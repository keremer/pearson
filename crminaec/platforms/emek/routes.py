from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import or_

from crminaec.core.models import db
from crminaec.platforms.emek.models import Item, ItemComposition, PriceSource

# Create the Blueprint for the new EMEK Micro-SaaS
emek_bp = Blueprint('emek', __name__, url_prefix='/emek')

# --- ROUTES ---bom_editor, get_catalog, get_tree_data, get_item_details, search_items, add_component, where_used, update_item, remove_component

@emek_bp.route('/bom-editor')
def bom_editor():
    """Renders the HTML interface we built earlier."""
    return render_template('emek/bom_editor.html')
#-----------------------------------------------------------------------------
@emek_bp.route('/api/catalog', methods=['GET'])
def get_catalog():
    """Returns a paginated and searchable list of items using native SQLAlchemy."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search_query = request.args.get('search', '', type=str)
    
    # 1. Start a native DB Session Query
    query = db.session.query(Item)
    
    # 2. Apply search filter safely using standard SQLAlchemy 'or_'
    if search_query:
        query = query.filter(
            or_(
                Item.code.ilike(f'%{search_query}%'),
                Item.name.ilike(f'%{search_query}%')
            )
        )
        
    # 3. Manual Pagination (Bulletproof)
    total_count = query.count()
    items = query.order_by(Item.code).offset((page - 1) * per_page).limit(per_page).all()
    has_next = (page * per_page) < total_count
    
    # 4. Serialize the data
    catalog = []
    # 4. Serialize the data
    catalog = []
    for item in items:
        # Check if it has children
        is_compound = len(item.children_links) > 0
        catalog.append({
            'id': item.item_id,
            'code': item.code,
            'name': item.name,
            'is_compound': is_compound,
            # Tell the frontend if it's a category so we can hide the quantity box!
            'is_category': getattr(item, 'is_category', False) 
        })
        
    # 5. Return JSON to Javascript
    return jsonify({
        'items': catalog,
        'has_next': has_next,
        'current_page': page
    })
#-----------------------------------------------------------------------------
@emek_bp.route('/api/get_tree_data')
def get_tree_data():
    """Builds the tree, ensuring branches are properly collapsible (+)"""
    item_id = request.args.get('item_id', type=int)
    if not item_id: return jsonify([])

    root_item = db.session.get(Item, item_id)
    if not root_item: return jsonify([])

    tree_data = []

    def build_node(item, parent_node_id="#", path_id=""):
        current_node_id = f"{path_id}_{item.item_id}" if path_id else str(item.item_id)

        # 1. VISUAL FIX: Differentiate between Categories, Physical Assemblies, and Raw Materials
        if getattr(item, 'is_category', False):
            # It's a classification compound
            icon = "fas fa-folder text-info"  # Blue Folder
        elif len(item.children_links) > 0:
            # It's a physical compound/assembly
            icon = "fas fa-box text-warning"  # Yellow Box
        else:
            # It's a raw material
            icon = "fas fa-cog text-secondary" # Gray Cog

        node = {
            "id": current_node_id,
            "parent": parent_node_id,
            "text": f"<b>[{item.code}]</b> {item.name}",
            "icon": icon,
            "state": {"opened": parent_node_id == "#"}, 
            "data": {"real_item_id": item.item_id}
        }

        tree_data.append(node)

        # Recursively build branches
        for comp in item.children_links:
            build_node(comp.child_item, current_node_id, current_node_id)

    build_node(root_item)
    return jsonify(tree_data)
#-----------------------------------------------------------------------------
@emek_bp.route('/api/get_item_details/<string:node_id>')
def get_item_details(node_id):
    """
    Fetches the details and immediate children for the right-hand window.
    """
    real_item_id = int(node_id.split('_')[-1])
    item = db.session.get(Item, real_item_id)
    
    if not item:
        return jsonify({"error": "Öğe bulunamadı (Item not found)"}), 404

    components = []
    for comp in item.children_links:
        child = comp.child_item
        components.append({
            "child_id": child.item_id,
            "code": child.code,
            "name": child.name,
            "qty": float(comp.quantity or 0.0),
            # This calls the recursive property we just added!
            "unit_cost": float(child.total_cost or 0.0) 
        })

    return jsonify({
        "item_id": item.item_id,
        "code": item.code,                                    # <-- ADD THIS
        "name": item.name,
        "is_category": getattr(item, 'is_category', False),   # <-- ADD THIS
        "total_cost": float(item.total_cost or 0.0), 
        "components": components
    })
#-----------------------------------------------------------------------------
@emek_bp.route('/api/search_items')
def search_items():
    """Takes a search query (q) and returns matching items instantly."""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([]) # Don't search until they type at least 2 characters

    # Search in both the 'code' and 'name' columns (case-insensitive)
    results = Item.query.filter(
        or_(
            Item.code.ilike(f"%{query}%"),
            Item.name.ilike(f"%{query}%")
        )
    ).limit(10).all() # Only bring back the top 10 to keep it lightning fast

    # Return a flat list of dictionaries for the frontend
    return jsonify([{
        "item_id": item.item_id,
        "code": item.code,
        "name": item.name,
        "unit_cost": item.total_cost # Use your recursive property!
    } for item in results])
#-----------------------------------------------------------------------------
@emek_bp.route('/api/add_component', methods=['POST'])
def add_component():
    """Links a child item to a parent item."""
    # Use get_json() and fallback to an empty dict if it returns None
    data = request.get_json() or {}
    
    parent_id = data.get('parent_id')
    child_id = data.get('child_id')
    
    # Catch empty strings and provide a default of 1.0
    try:
        qty = float(data.get('qty') or 1.0)
    except ValueError:
        qty = 1.0

    parent = db.session.get(Item, parent_id)
    child = db.session.get(Item, child_id)

    if not parent or not child:
        return jsonify({"error": "Öğe bulunamadı (Item not found)"}), 404

    try:
        # This calls our bulletproof safety check!
        parent.add_component(child, qty)
        db.session.commit()
        return jsonify({"success": True, "message": "Bileşen eklendi!"})
    except ValueError as e:
        # Catches the Circular Dependency error
        return jsonify({"error": str(e)}), 400

#-----------------------------------------------------------------------------
@emek_bp.route('/api/where_used/<int:item_id>')
def where_used(item_id):
    """Reverse Lookup: Finds all parent items that consume this item."""
    # Query the association table in reverse! 
    # Give me all rows where this item is the CHILD.
    compositions = db.session.query(ItemComposition).filter_by(child_id=item_id).all()
    
    results = []
    for comp in compositions:
        parent = comp.parent_item
        results.append({
            "id": parent.item_id,
            "code": parent.code,
            "name": parent.name,
            "qty_used": comp.quantity
        })
        
    return jsonify(results)
#-----------------------------------------------------------------------------
@emek_bp.route('/api/update_item/<int:item_id>', methods=['POST'])
def update_item(item_id):
    """Updates an item's details, including the is_category Phantom switch."""
    item = db.session.get(Item, item_id)
    if not item: return jsonify({"error": "Item not found"}), 404

    data = request.get_json()
    
    # Update fields (using .get() with fallbacks)
    item.code = data.get('code', item.code)
    item.name = data.get('name', item.name)
    item.base_cost = float(data.get('base_cost', item.base_cost or 0.0))
    
    # Toggle the Phantom Category switch
    item.is_category = bool(data.get('is_category', False))

    db.session.commit()
    return jsonify({"success": True})
#-----------------------------------------------------------------------------
@emek_bp.route('/api/remove_component', methods=['POST'])
def remove_component():
    """Unlinks a child item from a parent item."""
    data = request.get_json()
    parent_id = data.get('parent_id')
    child_id = data.get('child_id')

    # Find the specific link between these two items
    link = db.session.query(ItemComposition).filter_by(parent_id=parent_id, child_id=child_id).first()
    
    if link:
        db.session.delete(link)
        db.session.commit()
        return jsonify({"success": True})
        
    return jsonify({"error": "Bağlantı bulunamadı (Link not found)"}), 404
#-----------------------------------------------------------------------------
@emek_bp.route('/api/utility/fix_inverted_categories')
def fix_inverted_categories():
    """
    A one-time utility script to sweep the database and flip inverted parent-child relationships.
    Finds instances where a Category is mistakenly listed as a Child of a physical item.
    """
    all_links = db.session.query(ItemComposition).all()
    fixes_made = 0
    
    for link in all_links:
        # We grab the actual FULL Python objects, not just the IDs
        old_parent = link.parent_item
        old_child = link.child_item
        
        # Check for the Paradox: Is the Child a Folder, but the Parent is just a Box?
        if old_child.is_category == True and old_parent.is_category == False:
            
            qty = link.quantity
            
            # Destroy the inverted legacy link
            db.session.delete(link)
            db.session.flush() 
            
            # Create the correct link using the strict objects (Pylance will love this)
            new_link = ItemComposition(
                parent_item=old_child,  # The old child object is now the Parent!
                child_item=old_parent,  # The old parent object is now the Child!
                quantity=qty
            )
            db.session.add(new_link)
            fixes_made += 1
            
    # Lock in the changes
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "message": f"Veritabanı tarandı. {fixes_made} adet ters ilişki başarıyla düzeltildi! (Scanned DB. Fixed {fixes_made} inverted relationships!)"
    })

#Services
#-----------------------------------------------------------------------------
def process_prosap_quote(full_sku: str, prosap_total_price: float):
    """
    Parses an 8-part SKU, subtracts known accessory costs, 
    and infers the baseline cabinet cost.
    
    Example SKU: M7045B01.WHT.B.R5-NAV.S10.MWHT.STR-B.SENS-D
    """
    parts = full_sku.split('.')
    
    # Ensure we have a valid 8-part EMEK SKU
    if len(parts) != 8:
        raise ValueError("Geçersiz SKU Formatı (Invalid SKU Format)")

    # Extract the components
    carcass = parts[0]
    body_color = parts[1]
    side_pos = parts[2]
    side_model = parts[3]
    door_model = parts[4]
    door_color = parts[5]
    light_code = parts[6]
    sensor_code = parts[7]

    # 1. Define the "Baseline Cabinet" (Carcass + Body Color + Door)
    baseline_sku = f"{carcass}.{body_color}.{door_model}.{door_color}"
    
    # 2. Identify the Accessories
    # (In a real app, you would query the DB for these items: db.session.query(Item).filter_by(code=...))
    accessories = [
        {"code": f"SIDE.{side_pos}.{side_model}", "cost": 800.0, "reliability": 100}, # Example DB lookups
        {"code": f"LIGHT.{light_code}", "cost": 500.0, "reliability": 100},
        {"code": f"SENS.{sensor_code}", "cost": 200.0, "reliability": 90}
    ]

    # 3. Calculate known accessory costs
    # Only subtract if the accessory is actually present (not "00" or "NONE")
    known_accessory_cost = 0.0
    for acc in accessories:
        if "00" not in acc["code"] and "NONE" not in acc["code"]:
            known_accessory_cost += acc["cost"]

    # 4. INFER THE BASELINE COST
    inferred_baseline_cost = prosap_total_price - known_accessory_cost

    # 5. Save or Update the Baseline Item in EMEK
    baseline_item = db.session.query(Item).filter_by(code=baseline_sku).first()
    
    if not baseline_item:
        # Create it!
        baseline_item = Item(
            code=baseline_sku,
            name=f"Base Cabinet {carcass} ({door_model})",
            base_cost=inferred_baseline_cost,
            price_source=PriceSource.INFERRED,
            reliability_score=60  # It's an inference, so we trust it 60%
        )
        db.session.add(baseline_item)
    else:
        # If it exists but was a Legacy import, upgrade its price and score!
        if baseline_item.reliability_score < 80:
            baseline_item.base_cost = inferred_baseline_cost
            baseline_item.price_source = PriceSource.INFERRED
            baseline_item.reliability_score = 75 # Bumping the score as we get more data

    db.session.commit()
    
    return baseline_item