import os
import re
import unicodedata
import uuid

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from crminaec.core.models import db
from crminaec.platforms.emek.models import (Item, ItemAttachment,
                                            ItemComposition, PriceSource)

# Create the Blueprint for the new EMEK Micro-SaaS
emek_bp = Blueprint('emek', __name__, url_prefix='/emek')

# --- ROUTES ---

@emek_bp.route('/bom-editor')
def bom_editor():
    """Renders the HTML interface for BoQ management. The frontend will handle all interactions via AJAX."""
    return render_template('emek/bom_editor.html')

#-----------------------------------------------------------------------------
@emek_bp.route('/api/catalog', methods=['GET'])
def get_catalog():
    """Returns a paginated and searchable list of items using native SQLAlchemy."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search_query = request.args.get('search', '', type=str)
    
    query = db.session.query(Item)
    
    if search_query:
        query = query.filter(
            or_(
                Item.code.ilike(f'%{search_query}%'),
                Item.name.ilike(f'%{search_query}%')
            )
        )
        
    total_count = query.count()
    items = query.order_by(Item.code).offset((page - 1) * per_page).limit(per_page).all()
    has_next = (page * per_page) < total_count
    
    catalog = []
    for item in items:
        is_compound = len(item.children_links) > 0
        catalog.append({
            'id': item.item_id,
            'code': item.code,
            'name': item.name,
            'is_compound': is_compound,
            'is_category': getattr(item, 'is_category', False) 
        })
        
    return jsonify({
        'items': catalog,
        'has_next': has_next,
        'current_page': page
    })

#-----------------------------------------------------------------------------
@emek_bp.route('/api/get_tree_data')
def get_tree_data():
    """Handles both Initial Load (Roots) and Lazy Loading (Branches) for jsTree."""
    # jsTree natively sends '?id=' when expanding a branch
    node_id = request.args.get('id')
    item_id = request.args.get('item_id', type=int)

    # 1. PARSE ID: If jsTree asked for a specific branch
    if node_id and node_id != '#':
        # Extract the actual database ID from our structured node IDs (e.g., "1_4_5" -> 5)
        item_id = int(node_id.split('_')[-1])

    # 2. INITIAL LOAD: Return only the top-level Roots
    if not item_id or node_id == '#':
        subquery = db.session.query(ItemComposition.child_id)
        roots = db.session.query(Item).filter(~Item.item_id.in_(subquery)).all()
        
        tree_data = []
        for root in roots:
            if getattr(root, 'is_category', False):
                tree_data.append({
                    "id": str(root.item_id),
                    "text": f"<b>[{root.code}]</b> {root.name}",
                    "icon": "fas fa-folder text-primary",
                    "children": True, # Tells jsTree to render a clickable '+' arrow
                    "data": {"real_item_id": root.item_id}
                })
        return jsonify(tree_data)

    # 3. LAZY LOAD: Return only the immediate children of the clicked folder
    parent_item = db.session.get(Item, item_id)
    if not parent_item: return jsonify([])

    tree_data = []
    for comp in parent_item.children_links:
        child = comp.child_item
        # Maintain a unique path for the DOM so the same screw can appear in 10 cabinets
        current_node_id = f"{node_id}_{child.item_id}" if node_id and node_id != '#' else str(child.item_id)
        
        is_cat = getattr(child, 'is_category', False)
        has_kids = len(child.children_links) > 0

        # Visual hierarchy
        if is_cat:
            icon = "fas fa-folder text-info"
        elif has_kids:
            icon = "fas fa-box text-warning"
        else:
            icon = "fas fa-cog text-secondary"

        tree_data.append({
            "id": current_node_id,
            "text": f"<b>[{child.code}]</b> {child.name}",
            "icon": icon,
            "children": is_cat or has_kids, # Only render '+' arrow if it has contents
            "data": {"real_item_id": child.item_id}
        })

    return jsonify(tree_data)

#-----------------------------------------------------------------------------
@emek_bp.route('/api/get_item_details/<string:node_id>')
def get_item_details(node_id):
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
            "unit_cost": float(child.total_cost or 0.0) 
        })

    return jsonify({
        "item_id": item.item_id,
        "code": item.code,
        "name": item.name,
        "is_category": getattr(item, 'is_category', False),
        "total_cost": float(item.total_cost or 0.0), 
        "components": components,
        "technical_specs": item.technical_specs if hasattr(item, 'technical_specs') else {}
    })

#-----------------------------------------------------------------------------
@emek_bp.route('/api/search_items')
def search_items():
    query = request.args.get('q', '').strip()
    
    if len(query) < 2: return jsonify([])

    results = Item.query.filter(
        or_(
            Item.code.ilike(f"%{query}%"),
            Item.name.ilike(f"%{query}%")
        )
    ).limit(10).all() 

    return jsonify([{
        "item_id": item.item_id,
        "code": item.code,
        "name": item.name,
        "unit_cost": item.total_cost 
    } for item in results])

#-----------------------------------------------------------------------------
@emek_bp.route('/api/create_item', methods=['POST'])
def create_item():
    """Creates a new item or folder. If parent_id is missing, it becomes a Root."""
    data = request.get_json() or {}
    code = data.get('code', '').strip()
    name = data.get('name', '').strip()
    is_category = bool(data.get('is_category', True))
    parent_id = data.get('parent_id')

    if not code or not name:
        return jsonify({"error": "Poz/Kod ve Tanım zorunludur."}), 400

    existing = db.session.query(Item).filter_by(code=code).first()
    if existing:
        return jsonify({"error": "Bu koda sahip bir öğe zaten mevcut."}), 400

    new_item = Item(code=code, name=name, is_category=is_category, base_cost=0.0)
    db.session.add(new_item)
    db.session.flush()

    if parent_id:
        parent = db.session.get(Item, parent_id)
        # STRICT PYLANCE CHECK
        if parent is not None:
            try:
                parent.add_component(new_item, 1.0)
            except ValueError as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 400

    db.session.commit()
    return jsonify({"success": True, "item_id": new_item.item_id})

#-----------------------------------------------------------------------------
@emek_bp.route('/api/add_component', methods=['POST'])
def add_component():
    data = request.get_json() or {}
    parent_id = data.get('parent_id')
    child_id = data.get('child_id')
    
    try:
        qty = float(data.get('qty') or 1.0)
    except ValueError:
        qty = 1.0

    parent = db.session.get(Item, parent_id)
    child = db.session.get(Item, child_id)

    # STRICT PYLANCE CHECK: Explicitly ensure neither is None
    if parent is None or child is None:
        return jsonify({"error": "Öğe bulunamadı (Item not found)"}), 404

    try:
        # Pylance now knows parent is safely an Item
        parent.add_component(child, qty)
        db.session.commit()
        return jsonify({"success": True, "message": "Bileşen eklendi!"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

#-----------------------------------------------------------------------------
@emek_bp.route('/api/where_used/<int:item_id>')
def where_used(item_id):
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
    item = db.session.get(Item, item_id)
    if not item: return jsonify({"error": "Item not found"}), 404

    data = request.get_json() or {}
    item.code = data.get('code', item.code)
    item.name = data.get('name', item.name)
    item.base_cost = float(data.get('base_cost', item.base_cost or 0.0))
    item.is_category = bool(data.get('is_category', False))

    db.session.commit()
    return jsonify({"success": True})

#-----------------------------------------------------------------------------
@emek_bp.route('/api/move_node', methods=['POST'])
def move_node():
    data = request.get_json() or {}
    child_id = data.get('child_id')
    old_parent_id = data.get('old_parent_id')
    new_parent_id = data.get('new_parent_id')

    if not all([child_id, old_parent_id, new_parent_id]):
        return jsonify({"error": "Eksik parametre (Missing parameters)"}), 400

    old_link = db.session.query(ItemComposition).filter_by(
        parent_id=old_parent_id, child_id=child_id
    ).first()

    if not old_link:
        return jsonify({"error": "Eski bağlantı bulunamadı (Old link not found)"}), 404

    new_parent = db.session.get(Item, new_parent_id)
    child = db.session.get(Item, child_id)
    
    # STRICT PYLANCE CHECK: Crucial fix for line 284!
    if new_parent is None or child is None:
        return jsonify({"error": "Hedef klasör veya öğe bulunamadı."}), 404

    qty = old_link.quantity

    try:
        # Pylance is happy: new_parent is guaranteed to be an Item here
        new_parent.add_component(child, qty) 
        
        # If add_component succeeds without raising a ValueError, delete the old link
        db.session.delete(old_link)
        db.session.commit()
        return jsonify({"success": True})
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

#-----------------------------------------------------------------------------
@emek_bp.route('/api/remove_component', methods=['POST'])
def remove_component():
    data = request.get_json() or {}
    parent_id = data.get('parent_id')
    child_id = data.get('child_id')

    link = db.session.query(ItemComposition).filter_by(parent_id=parent_id, child_id=child_id).first()
    
    if link:
        db.session.delete(link)
        db.session.commit()
        return jsonify({"success": True})
        
    return jsonify({"error": "Bağlantı bulunamadı (Link not found)"}), 404

#-----------------------------------------------------------------------------
@emek_bp.route('/api/utility/fix_inverted_categories')
def fix_inverted_categories():
    all_links = db.session.query(ItemComposition).all()
    fixes_made = 0
    
    for link in all_links:
        old_parent = link.parent_item
        old_child = link.child_item
        
        if old_child.is_category == True and old_parent.is_category == False:
            qty = link.quantity
            db.session.delete(link)
            db.session.flush() 
            
            new_link = ItemComposition(
                parent_item=old_child,  
                child_item=old_parent,  
                quantity=qty
            )
            db.session.add(new_link)
            fixes_made += 1
            
    db.session.commit()
    return jsonify({"success": True, "message": f"{fixes_made} adet ters ilişki başarıyla düzeltildi!"})

#-----------------------------------------------------------------------------
@emek_bp.route('/api/upload_attachment/<int:item_id>', methods=['POST'])
def upload_attachment(item_id):
    item = db.session.get(Item, item_id)
    if not item: return jsonify({"error": "Item not found"}), 404

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    safe_filename = str(file.filename) if file.filename else ""
    
    if not safe_filename:
        return jsonify({"error": "No selected file"}), 400

    upload_folder = os.path.join('crminaec', 'static', 'uploads', 'items')
    os.makedirs(upload_folder, exist_ok=True)

    semantic_name = make_semantic_filename(item.code, item.name, safe_filename)
    file_path = os.path.join(upload_folder, semantic_name)
    file.save(file_path)

    ext = semantic_name.rsplit('.', 1)[-1].lower()
    file_type = "image" if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "document"

    db_path = f"/static/uploads/items/{semantic_name}" 
    new_attachment = ItemAttachment(
        original_filename=safe_filename,
        semantic_filename=semantic_name,
        file_path=db_path,
        file_type=file_type
    )
    item.attachments.append(new_attachment)
    db.session.commit()

    return jsonify({"success": True, "file": {"name": semantic_name, "path": db_path, "type": file_type}})


@emek_bp.route('/api/get_attachments/<int:item_id>')
def get_attachments(item_id):
    item = db.session.get(Item, item_id)
    if not item: return jsonify([])

    results = []
    for att in item.attachments:
        results.append({
            "id": att.attachment_id,
            "semantic_filename": att.semantic_filename,
            "path": att.file_path,
            "type": att.file_type
        })
    return jsonify(results)

# --- SERVICES ---
#-----------------------------------------------------------------------------
def process_prosap_quote(full_sku: str, prosap_total_price: float):
    parts = full_sku.split('.')
    if len(parts) != 8:
        raise ValueError("Geçersiz SKU Formatı (Invalid SKU Format)")

    carcass, body_color, side_pos, side_model, door_model, door_color, light_code, sensor_code = parts
    baseline_sku = f"{carcass}.{body_color}.{door_model}.{door_color}"
    
    accessories = [
        {"code": f"SIDE.{side_pos}.{side_model}", "cost": 800.0, "reliability": 100}, 
        {"code": f"LIGHT.{light_code}", "cost": 500.0, "reliability": 100},
        {"code": f"SENS.{sensor_code}", "cost": 200.0, "reliability": 90}
    ]

    known_accessory_cost = sum([acc["cost"] for acc in accessories if "00" not in acc["code"] and "NONE" not in acc["code"]])
    inferred_baseline_cost = prosap_total_price - known_accessory_cost

    baseline_item = db.session.query(Item).filter_by(code=baseline_sku).first()
    
    if not baseline_item:
        baseline_item = Item(
            code=baseline_sku,
            name=f"Base Cabinet {carcass} ({door_model})",
            base_cost=inferred_baseline_cost,
            price_source=PriceSource.INFERRED,
            reliability_score=60 
        )
        db.session.add(baseline_item)
    else:
        if baseline_item.reliability_score < 80:
            baseline_item.base_cost = inferred_baseline_cost
            baseline_item.price_source = PriceSource.INFERRED
            baseline_item.reliability_score = 75 

    db.session.commit()
    return baseline_item

def make_semantic_filename(item_code, item_name, original_filename):
    ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
    clean_name = unicodedata.normalize('NFKD', item_name).encode('ASCII', 'ignore').decode('utf-8')
    clean_code = unicodedata.normalize('NFKD', item_code).encode('ASCII', 'ignore').decode('utf-8')
    clean_name = re.sub(r'[^\w\s-]', '', clean_name).strip().replace(' ', '_')
    clean_code = re.sub(r'[^\w\s-]', '', clean_code).strip().replace(' ', '_')
    short_hash = str(uuid.uuid4())[:4]
    new_name = f"{clean_code}_{clean_name}_{short_hash}.{ext}"
    return secure_filename(new_name)