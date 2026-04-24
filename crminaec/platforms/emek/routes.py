import csv
import io
import os
import re
import unicodedata
import uuid

from flask import (Blueprint, Response, current_app, jsonify, render_template,
                   request)
from flask_login import login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from crminaec.core.models import db
from crminaec.core.security import role_required
from crminaec.platforms.emek.models import (Item, ItemAttachment,
                                            ItemComposition, NodeType,
                                            PriceSource)

# Create the Blueprint for the new EMEK Micro-SaaS
emek_bp = Blueprint('emek', __name__, url_prefix='/emek')

# --- ROUTES ---

@emek_bp.route('/bom-editor')
@login_required
@role_required('admin', 'power_user')
def bom_editor():
    """Renders the HTML interface for BoQ management. The frontend will handle all interactions via AJAX."""
    return render_template('emek/bom_editor.html')

#-----------------------------------------------------------------------------
@emek_bp.route('/api/catalog', methods=['GET'])
@login_required
@role_required('admin', 'power_user')
def get_catalog():
    """Returns a paginated and searchable list of items using native SQLAlchemy."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search_query = request.args.get('search', '', type=str)
    item_type_filter = request.args.get('type', '', type=str)
    
    query = db.select(Item).filter(
        Item.is_deleted.is_not(True),
        Item.is_archived.is_not(True)
    )
    
    if search_query:
        query = query.filter(
            or_(
                Item.code.ilike(f'%{search_query}%'),
                Item.name.ilike(f'%{search_query}%')
            )
        )
        
    if item_type_filter:
        query = query.filter(Item.item_type == item_type_filter)
        
    total_count = db.session.scalar(db.select(db.func.count()).select_from(query.subquery())) or 0
    items = db.session.scalars(query.order_by(Item.code).offset((page - 1) * per_page).limit(per_page)).all()
    has_next = (page * per_page) < total_count
    
    catalog = []
    for item in items:
        is_compound = len(item.children_links) > 0
        catalog.append({
            'id': item.item_id,
            'code': item.code,
            'name': item.name,
            'is_compound': is_compound,
            'is_category': getattr(item, 'is_category', False),
            'item_type': item.item_type,
            'node_type': item.node_type.value if item.node_type else ''
        })
        
    return jsonify({
        'items': catalog,
        'has_next': has_next,
        'current_page': page
    })

#-----------------------------------------------------------------------------
@emek_bp.route('/api/get_tree_data')
@login_required
@role_required('admin', 'power_user')
def get_tree_data():
    """Handles both Initial Load (Roots) and Lazy Loading (Branches) for jsTree."""
    # jsTree natively sends '?id=' when expanding a branch
    node_id = request.args.get('id')
    item_id = request.args.get('item_id', type=int)
    show_archived = request.args.get('show_archived', '0') == '1'

    # 1. PARSE ID: If jsTree asked for a specific branch
    if node_id and node_id != '#':
        # Extract the actual database ID from our structured node IDs (e.g., "1_4_5" -> 5)
        item_id = int(node_id.split('_')[-1])

    # 2. INITIAL LOAD: Return only the top-level Roots
    if not item_id or node_id == '#':
        subquery = db.select(ItemComposition.child_id)
        
        filter_conditions = [~Item.item_id.in_(subquery), Item.is_deleted.is_not(True)]
        if not show_archived:
            filter_conditions.append(Item.is_archived.is_not(True))
            
        roots = db.session.scalars(db.select(Item).filter(*filter_conditions)).all()
        
        tree_data = []
        for root in roots:
            if getattr(root, 'is_category', False):
                is_archived = getattr(root, 'is_archived', False)
                name_html = f"<span class='text-muted text-decoration-line-through'>{root.name}</span> <span class='badge bg-warning text-dark ms-1' style='font-size:0.65rem;'>Arşiv</span>" if is_archived else root.name
                
                tree_data.append({
                    "id": str(root.item_id),
                    "text": f"<b>[{root.code}]</b> {name_html}",
                    "icon": "fas fa-folder text-primary" if root.node_type and root.node_type.name == 'CATEGORY' else "fas fa-layer-group text-info",
                    "children": True, # Tells jsTree to render a clickable '+' arrow
                    "data": {
                        "real_item_id": root.item_id,
                        "item_type": root.item_type,
                        "node_type": root.node_type.value if root.node_type else "",
                        "is_archived": is_archived
                    }
                })
        return jsonify(tree_data)

    # 3. LAZY LOAD: Return only the immediate children of the clicked folder
    parent_item = db.session.get(Item, item_id)
    if not parent_item: return jsonify([])

    tree_data = []
    for comp in parent_item.children_links:
        child = comp.child_item
        
        # Filter out logically removed items organically
        if getattr(child, 'is_deleted', False):
            continue
        if not show_archived and getattr(child, 'is_archived', False):
            continue
            
        # Maintain a unique path for the DOM so the same screw can appear in 10 cabinets
        current_node_id = f"{node_id}_{child.item_id}" if node_id and node_id != '#' else str(child.item_id)
        
        is_cat = getattr(child, 'is_category', False) or (child.node_type and child.node_type.name == 'CATEGORY')
        has_kids = len(child.children_links) > 0

        # Smart Visual Hierarchy based on Universal Graph Model
        if is_cat:
            icon = "fas fa-folder text-info"
        elif child.item_type == 'course':
            icon = "fas fa-graduation-cap text-primary"
        elif child.item_type == 'lesson':
            icon = "fas fa-chalkboard-teacher text-success"
        elif has_kids:
            icon = "fas fa-box text-warning"
        else:
            icon = "fas fa-cog text-secondary"

        is_archived = getattr(child, 'is_archived', False)
        name_html = f"<span class='text-muted text-decoration-line-through'>{child.name}</span> <span class='badge bg-warning text-dark ms-1' style='font-size:0.65rem;'>Arşiv</span>" if is_archived else child.name

        tree_data.append({
            "id": current_node_id,
            "text": f"<b>[{child.code}]</b> {name_html}",
            "icon": icon,
            "children": is_cat or has_kids, # Only render '+' arrow if it has contents
            "data": {
                "real_item_id": child.item_id,
                "item_type": child.item_type,
                "node_type": child.node_type.value if child.node_type else "",
                "is_archived": is_archived
            }
        })

    return jsonify(tree_data)

#-----------------------------------------------------------------------------
@emek_bp.route('/api/get_item_details/<string:node_id>')
@login_required
@role_required('admin', 'power_user')
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
            "unit_cost": float(child.total_cost or 0.0),
            "is_archived": getattr(child, 'is_archived', False)
        })

    return jsonify({
        "item_id": item.item_id,
        "code": item.code,
        "name": item.name,
        "item_type": item.item_type,
        "node_type": item.node_type.value if item.node_type else "",
        "is_category": getattr(item, 'is_category', False),
        "is_archived": getattr(item, 'is_archived', False),
        "base_cost": float(item.base_cost or 0.0),
        "total_cost": float(item.total_cost or 0.0), 
        "dim_x": item.dim_x,
        "dim_y": item.dim_y,
        "dim_z": item.dim_z,
        "components": components,
        "technical_specs": item.technical_specs if hasattr(item, 'technical_specs') and item.technical_specs else {}
    })

#-----------------------------------------------------------------------------
@emek_bp.route('/api/search_items')
@login_required
@role_required('admin', 'power_user')
def search_items():
    query = request.args.get('q', '').strip()
    item_type_filter = request.args.get('type', '').strip()
    show_archived = request.args.get('show_archived', '0') == '1'
    
    if len(query) < 2: return jsonify([])

    query_stmt = db.select(Item).filter(
        Item.is_deleted.is_not(True),
        or_(
            Item.code.ilike(f"%{query}%"),
            Item.name.ilike(f"%{query}%")
        )
    )
    
    if not show_archived:
        query_stmt = query_stmt.filter(Item.is_archived.is_not(True))
        
    if item_type_filter:
        query_stmt = query_stmt.filter(Item.item_type == item_type_filter)
        
    results = db.session.scalars(query_stmt.limit(10)).all()

    return jsonify([{
        "item_id": item.item_id,
        "code": item.code,
        "name": item.name,
        "item_type": item.item_type,
        "node_type": item.node_type.value if item.node_type else "",
        "unit_cost": item.total_cost,
        "is_archived": getattr(item, 'is_archived', False)
    } for item in results])

#-----------------------------------------------------------------------------
@emek_bp.route('/api/create_item', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def create_item():
    """Creates a new item or folder. If parent_id is missing, it becomes a Root."""
    data = request.get_json() or {}
    code = data.get('code', '').strip()
    name = data.get('name', '').strip()
    is_category = bool(data.get('is_category', True))
    item_type = data.get('item_type', 'raw_material')
    node_type_str = data.get('node_type', 'PRODUCT')
    parent_id = data.get('parent_id')

    if not code or not name:
        return jsonify({"error": "Poz/Kod ve Tanım zorunludur."}), 400

    existing = db.session.scalar(db.select(Item).filter_by(code=code))
    if existing:
        return jsonify({"error": "Bu koda sahip bir öğe zaten mevcut."}), 400

    node_type = getattr(NodeType, node_type_str.upper(), NodeType.PRODUCT)

    new_item = Item(**{
        'code': code, 
        'name': name, 
        'is_category': is_category, 
        'base_cost': 0.0,
        'item_type': item_type,
        'node_type': node_type
    })
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
@login_required
@role_required('admin', 'power_user')
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
@login_required
@role_required('admin', 'power_user')
def where_used(item_id):
    compositions = db.session.scalars(db.select(ItemComposition).filter_by(child_id=item_id)).all()
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
@login_required
@role_required('admin', 'power_user')
def update_item(item_id):
    item = db.session.get(Item, item_id)
    if not item: return jsonify({"error": "Item not found"}), 404

    data = request.get_json() or {}
    item.code = data.get('code', item.code)
    item.name = data.get('name', item.name)
    item.base_cost = float(data.get('base_cost', item.base_cost or 0.0))
    item.is_category = bool(data.get('is_category', False))
    
    item.dim_x = float(data.get('dim_x', item.dim_x or 0.0))
    item.dim_y = float(data.get('dim_y', item.dim_y or 0.0))
    item.dim_z = float(data.get('dim_z', item.dim_z or 0.0))
    
    if 'technical_specs' in data:
        item.technical_specs = data['technical_specs']

    db.session.commit()
    return jsonify({"success": True})

#-----------------------------------------------------------------------------
@emek_bp.route('/api/move_node', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def move_node():
    data = request.get_json() or {}
    child_id = data.get('child_id')
    old_parent_id = data.get('old_parent_id')
    new_parent_id = data.get('new_parent_id')

    if not all([child_id, old_parent_id, new_parent_id]):
        return jsonify({"error": "Eksik parametre (Missing parameters)"}), 400

    old_link = db.session.scalar(db.select(ItemComposition).filter_by(
        parent_id=old_parent_id, child_id=child_id
    ))

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
@login_required
@role_required('admin', 'power_user')
def remove_component():
    data = request.get_json() or {}
    parent_id = data.get('parent_id')
    child_id = data.get('child_id')

    link = db.session.scalar(db.select(ItemComposition).filter_by(parent_id=parent_id, child_id=child_id))
    
    if link:
        db.session.delete(link)
        db.session.commit()
        return jsonify({"success": True})
        
    return jsonify({"error": "Bağlantı bulunamadı (Link not found)"}), 404

#-----------------------------------------------------------------------------
@emek_bp.route('/api/utility/fix_inverted_categories')
@login_required
@role_required('admin', 'power_user')
def fix_inverted_categories():
    all_links = db.session.scalars(db.select(ItemComposition)).all()
    fixes_made = 0
    
    for link in all_links:
        old_parent = link.parent_item
        old_child = link.child_item
        
        if old_child.is_category == True and old_parent.is_category == False:
            qty = link.quantity
            db.session.delete(link)
            db.session.flush() 
            
            new_link = ItemComposition(**{
                'parent_item': old_child,  
                'child_item': old_parent,
                'quantity': qty,
                'optional_attributes': {}
            })
            db.session.add(new_link)
            fixes_made += 1
            
    db.session.commit()
    return jsonify({"success": True, "message": f"{fixes_made} adet ters ilişki başarıyla düzeltildi!"})

#-----------------------------------------------------------------------------
@emek_bp.route('/api/upload_attachment/<int:item_id>', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
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
    new_attachment = ItemAttachment(**{
        'original_filename': safe_filename,
        'semantic_filename': semantic_name,
        'file_path': db_path,
        'file_type': file_type
    })
    item.attachments.append(new_attachment)
    db.session.commit()

    return jsonify({"success": True, "file": {"name": semantic_name, "path": db_path, "type": file_type}})


@emek_bp.route('/api/get_attachments/<int:item_id>')
@login_required
@role_required('admin', 'power_user')
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

# --- MODERATOR & ADMIN ENTITY MANAGEMENT ---
@emek_bp.route('/api/delete_item/<int:item_id>', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if item:
        item.is_deleted = True
        db.session.commit()
    return jsonify({"success": True})

@emek_bp.route('/api/hard_delete_item/<int:item_id>', methods=['POST'])
@login_required
@role_required('admin')
def hard_delete_item(item_id):
    item = db.session.get(Item, item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return jsonify({"success": True})

@emek_bp.route('/api/archive_item/<int:item_id>', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def archive_item(item_id):
    item = db.session.get(Item, item_id)
    if item:
        item.is_archived = True
        db.session.commit()
    return jsonify({"success": True})

@emek_bp.route('/api/unarchive_item/<int:item_id>', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def unarchive_item(item_id):
    item = db.session.get(Item, item_id)
    if item:
        item.is_archived = False
        db.session.commit()
    return jsonify({"success": True})

@emek_bp.route('/api/export_bom_csv/<int:item_id>')
@login_required
@role_required('admin', 'power_user')
def export_bom_csv(item_id):
    """Exports the full, recursive BoM of an item to a CSV file."""
    item = db.session.get(Item, item_id)
    if not item:
        return "Item not found", 404

    # --- DYNAMIC SPEC TRAVERSAL ---
    all_spec_keys = set()
    def collect_all_specs(current_item):
        """Recursively find all unique keys in technical_specs."""
        if current_item.technical_specs:
            all_spec_keys.update(current_item.technical_specs.keys())
        for link in current_item.children_links:
            if link.child_item:
                collect_all_specs(link.child_item)
    
    collect_all_specs(item)
    sorted_spec_keys = sorted(list(all_spec_keys))

    # Recursive helper function to build a flat list from the hierarchy
    def build_bom_flat_list(current_item, quantity, level, bom_list):
        row_data = {
            'Level': level,
            'Code': current_item.code,
            'Name': current_item.name,
            'Quantity': quantity,
            'Unit Cost': current_item.total_cost,
            'Total Line Cost': (current_item.total_cost or 0) * quantity
        }
        # Add dynamic spec columns
        item_specs = current_item.technical_specs or {}
        for key in sorted_spec_keys:
            row_data[key] = item_specs.get(key, '')
        
        bom_list.append(row_data)

        # Recurse for children
        for link in current_item.children_links:
            if link.child_item:
                build_bom_flat_list(link.child_item, link.quantity, level + 1, bom_list)

    bom_data = []
    build_bom_flat_list(item, 1.0, 0, bom_data)

    output = io.StringIO()
    base_headers = ['Level', 'Code', 'Name', 'Quantity', 'Unit Cost', 'Total Line Cost']
    final_headers = base_headers + sorted_spec_keys
    # Use semicolon for better Excel compatibility with some European locales
    writer = csv.DictWriter(output, fieldnames=final_headers, delimiter=';')
    writer.writeheader()
    writer.writerows(bom_data)

    response = Response(b'\xef\xbb\xbf' + output.getvalue().encode('utf-8'), mimetype='text/csv')
    response.headers["Content-Disposition"] = f"attachment; filename=BOM_Export_{item.code}.csv"
    return response

@emek_bp.route('/api/import_csv', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def import_csv():
    """Imports items and compositions from uploaded CSV files."""
    if 'items_file' not in request.files:
        return jsonify({'error': 'Lütfen items.csv dosyasını yükleyin.'}), 400

    items_file = request.files['items_file']
    comps_file = request.files.get('comps_file')
    merge = request.form.get('merge', 'true').lower() == 'true'

    try:
        import json

        import pandas as pd
        from sqlalchemy.exc import IntegrityError

        # 1. Parse Items
        df_items = pd.read_csv(items_file.stream, sep=None, engine='python', dtype=str, encoding='utf-8-sig').fillna('')
        df_items.columns = [c.lower().strip() for c in df_items.columns]

        # 2. Parse Compositions (if provided)
        df_comps = None
        if comps_file and comps_file.filename:
            df_comps = pd.read_csv(comps_file.stream, sep=None, engine='python', dtype=str, encoding='utf-8-sig').fillna('')
            df_comps.columns = [c.lower().strip() for c in df_comps.columns]

        def parse_json(val_str):
            if not val_str: return {}
            try:
                val_str = str(val_str).replace('""', '"')
                return json.loads(val_str)
            except json.JSONDecodeError:
                return {}

        # Cache existing items to speed up lookups
        existing_items = db.session.execute(db.select(Item.item_id, Item.code, Item.name)).all()
        code_to_id = {item.code: item.item_id for item in existing_items}
        name_to_id = {item.name: item.item_id for item in existing_items}
        id_translation_map = {}

        # IMPORT ITEMS
        for _, row in df_items.iterrows():
            csv_id_str = row.get('item_id')
            if not csv_id_str: continue
            csv_id = int(csv_id_str)
            
            raw_code = str(row.get('code', '')).strip().upper()
            raw_name = str(row.get('name', '')).strip()
            if not raw_code: continue

            if db.session.get(Item, csv_id):
                id_translation_map[csv_id] = csv_id
                continue

            is_duplicate = raw_code in code_to_id or raw_name in name_to_id
            if is_duplicate:
                if merge:
                    matched_id = code_to_id.get(raw_code) or name_to_id.get(raw_name)
                    id_translation_map[csv_id] = matched_id
                    continue
                else:
                    if raw_code in code_to_id: raw_code = f"{raw_code}.{csv_id}"
                    if raw_name in name_to_id: raw_name = f"{raw_name}.{csv_id}"

            p_source_str = str(row.get('price_source', 'MANUAL')).upper()
            p_source = getattr(PriceSource, p_source_str, PriceSource.MANUAL)

            new_item = Item(**{
                'code': raw_code,
                'name': raw_name,
                'brand': str(row.get('brand', 'Generic')).strip() or 'Generic',
                'is_category': str(row.get('is_category', '')).lower() == 'true',
                'product_group': str(row.get('product_group', '')).strip() or None,
                'product_type': str(row.get('product_type', '')).strip() or None,
                'uom': str(row.get('uom', 'adet')).strip().lower() or 'adet',
                'dim_x': float(row.get('dim_x', 0.0) or 0.0),
                'dim_y': float(row.get('dim_y', 0.0) or 0.0),
                'dim_z': float(row.get('dim_z', 0.0) or 0.0),
                'base_cost': float(row.get('base_cost', 0.0) or 0.0),
                'technical_specs': parse_json(row.get('technical_specs')),
                'price_source': p_source,
                'reliability_score': int(row.get('reliability_score', 100) or 100)
            })
            new_item.item_id = csv_id
            db.session.add(new_item)
            
            code_to_id[raw_code] = csv_id
            name_to_id[raw_name] = csv_id
            id_translation_map[csv_id] = csv_id

        db.session.flush()

        # IMPORT COMPOSITIONS
        if df_comps is not None:
            for _, row in df_comps.iterrows():
                if not row.get('parent_id') or not row.get('child_id'): continue
                p_id = id_translation_map.get(int(row.get('parent_id', 0)))
                c_id = id_translation_map.get(int(row.get('child_id', 0)))
                if not p_id or not c_id: continue

                qty = float(row.get('quantity', 1.0) or 1.0)
                s_order = int(row.get('sort_order', 0) or 0)
                opt_attrs = parse_json(row.get('optional_attributes'))

                existing_link = db.session.scalar(db.select(ItemComposition).filter_by(parent_id=p_id, child_id=c_id))
                if existing_link: continue

                parent_obj = db.session.get(Item, p_id)
                child_obj = db.session.get(Item, c_id)
                if parent_obj and child_obj:
                    new_link = ItemComposition(**{
                        'parent_item': parent_obj,
                        'child_item': child_obj,
                        'quantity': qty,
                        'sort_order': s_order,
                        'optional_attributes': opt_attrs
                    })
                    db.session.add(new_link)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Toplu içe aktarım başarıyla tamamlandı!'})

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({'error': f'Veritabanı Çakışması (Integrity Error): {e.orig}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Beklenmeyen Hata: {str(e)}'}), 500

@emek_bp.route('/api/import_flat_bom/<int:parent_id>', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def import_flat_bom(parent_id):
    """Imports a flat Excel/CSV parts list directly into a selected parent node."""
    parent_item = db.session.get(Item, parent_id)
    if not parent_item:
        return jsonify({'error': 'Hedef klasör/ürün bulunamadı.'}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'Lütfen bir Excel veya CSV dosyası yükleyin.'}), 400

    file = request.files['file']
    filename = str(file.filename).lower()

    try:
        import pandas as pd
        if filename.endswith('.csv'):
            df = pd.read_csv(file.stream, sep=None, engine='python', dtype=str).fillna('')
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(file.stream, dtype=str).fillna('')
        else:
            return jsonify({'error': 'Desteklenmeyen format. Sadece .csv, .xlsx, .xls yükleyin.'}), 400

        # Smart Column Detection (Case insensitive, trims whitespace)
        col_map = {str(c).strip().lower(): str(c) for c in df.columns}
        
        code_col = next((col_map[c] for c in ['code', 'kod', 'pozno', 'item code', 'ürün kodu'] if c in col_map), None)
        name_col = next((col_map[c] for c in ['name', 'tanım', 'tanim', 'description', 'ürün adı'] if c in col_map), None)
        qty_col = next((col_map[c] for c in ['quantity', 'qty', 'miktar', 'adet'] if c in col_map), None)
        cost_col = next((col_map[c] for c in ['cost', 'price', 'fiyat', 'maliyet', 'birim fiyat'] if c in col_map), None)

        if not code_col or not name_col:
            return jsonify({'error': 'Dosyada "Kod" ve "Tanım" (veya benzeri) sütunlar bulunamadı.'}), 400

        imported_count = 0
        for _, row in df.iterrows():
            raw_code = str(row.get(code_col, '')).strip().upper()
            raw_name = str(row.get(name_col, '')).strip()
            if not raw_code: continue

            raw_qty = str(row.get(qty_col, '1')).replace(',', '.') if qty_col else '1'
            try: qty = float(raw_qty)
            except ValueError: qty = 1.0

            raw_cost = str(row.get(cost_col, '0')).replace(',', '.') if cost_col else '0'
            try: cost = float(raw_cost)
            except ValueError: cost = 0.0

            # Find or Create Item
            item = db.session.scalar(db.select(Item).filter_by(code=raw_code))
            if not item:
                item = Item(**{'code': raw_code, 'name': raw_name, 'base_cost': cost, 'is_category': False, 'item_type': 'raw_material', 'node_type': NodeType.PRODUCT})
                db.session.add(item)
                db.session.flush() # Get ID for relationships
            elif cost > 0 and (not item.base_cost or item.base_cost == 0):
                item.base_cost = cost # Update cost if it was missing

            # Link to Parent
            try:
                parent_item.add_component(item, qty)
                imported_count += 1
            except ValueError:
                pass # Ignore circular dependencies silently for bulk imports

        db.session.commit()
        return jsonify({'success': True, 'message': f'{imported_count} kalem başarıyla "{parent_item.name}" altına aktarıldı!'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Hata: {str(e)}'}), 500

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

    baseline_item = db.session.scalar(db.select(Item).filter_by(code=baseline_sku))
    
    if not baseline_item:
        baseline_item = Item(**{
            'code': baseline_sku,
            'name': f"Base Cabinet {carcass} ({door_model})",
            'base_cost': inferred_baseline_cost,
            'price_source': PriceSource.INFERRED,
            'reliability_score': 60 
        })
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