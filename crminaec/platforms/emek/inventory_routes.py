"""
Inventory & Warehouse Management API
Handles Barcode/QR Code scanning and Stock Movement ledgers for mobile devices.
"""
import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request
from flask_login import login_required
from sqlalchemy import or_

from crminaec.core.models import db
from crminaec.core.security import role_required
from crminaec.platforms.emek.models import Item, MovementType, StockMovement

logger = logging.getLogger(__name__)

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/inventory')

@inventory_bp.route('/scanner', methods=['GET'])
@login_required
@role_required('admin', 'power_user')
def mobile_scanner():
    """Serves the frontend UI for the mobile barcode scanner."""
    recent_movements = db.session.scalars(
        db.select(StockMovement).order_by(StockMovement.timestamp.desc()).limit(5)
    ).all()
    return render_template('emek/scanner.html', recent_movements=recent_movements)

@inventory_bp.route('/print-label/<int:item_id>', methods=['GET'])
@login_required
@role_required('admin', 'power_user')
def print_label(item_id):
    """Generates a printable QR code label for a specific item."""
    item = db.session.get(Item, item_id)
    if not item:
        flash("Ürün bulunamadı (Item not found).", "danger")
        return redirect(request.referrer or '/emek/bom-editor')
        
    # Automatically assign a formal EMEK QR code if it doesn't have one
    if not item.qr_code:
        item.qr_code = f"EMEK-{item.item_id}-{item.code}"
        db.session.commit()
        
    return render_template('emek/print_label.html', item=item)

@inventory_bp.route('/scan/<path:scanned_code>', methods=['GET'])
@login_required
@role_required('admin', 'power_user')
def scan_item(scanned_code):
    """
    Lookup an item by its barcode, QR code, or internal SKU code.
    Used by mobile devices immediately after scanning a label.
    """
    # Search for an exact match in barcode, qr_code, or standard code
    item = db.session.scalar(
        db.select(Item).filter(
            or_(
                Item.barcode == scanned_code,
                Item.qr_code == scanned_code,
                Item.code == scanned_code
            )
        )
    )
    
    if not item:
        return jsonify({'error': 'Bu barkoda ait ürün bulunamadı (Item not found)'}), 404
        
    return jsonify({
        'item_id': item.item_id,
        'code': item.code,
        'name': item.name,
        'current_stock': item.stock_quantity,
        'uom': item.uom,
        'image_url': item.image_path
    })

@inventory_bp.route('/movement', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def record_movement():
    """
    Records a stock movement (IN, OUT, RETURN) into the ledger 
    and updates the master stock quantity.
    """
    data = request.get_json() or {}
    
    item_id = data.get('item_id')
    mov_type_str = data.get('movement_type', 'IN').upper()
    quantity = float(data.get('quantity', 0.0))
    
    if not item_id or quantity <= 0:
        return jsonify({'error': 'Geçerli bir ürün ID ve pozitif miktar zorunludur.'}), 400
        
    try:
        movement_type = MovementType[mov_type_str]
    except KeyError:
        return jsonify({'error': f'Geçersiz hareket tipi (Invalid movement type): {mov_type_str}'}), 400
        
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({'error': 'Ürün bulunamadı (Item not found).'}), 404
        
    # 1. Create the immutable Ledger Entry
    movement = StockMovement(**{
        'movement_type': movement_type,
        'quantity': quantity,
        'scanned_code': data.get('scanned_code'),
        'reference_document': data.get('reference_document'),
        'notes': data.get('notes')
    })
    item.stock_movements.append(movement)
    
    # 2. Automatically update the cached stock value
    if movement_type in [MovementType.IN, MovementType.RETURN]:
        item.stock_quantity += quantity
    elif movement_type == MovementType.OUT:
        item.stock_quantity -= quantity
    elif movement_type == MovementType.ADJUSTMENT:
        # For ADJ, we assume the quantity provided is a relative delta (either positive or negative)
        item.stock_quantity += quantity
        
    db.session.commit()
    
    logger.info(f"Stock {movement_type.name} recorded for {item.code}: {quantity} {item.uom}")
    
    return jsonify({
        'success': True,
        'message': 'Stok hareketi başarıyla kaydedildi.',
        'new_stock_quantity': item.stock_quantity,
        'movement': {
            'item_name': item.name,
            'type': movement_type.name,
            'quantity': quantity,
            'time': movement.timestamp.strftime('%H:%M') if movement.timestamp else ''
        }
    })

@inventory_bp.route('/sync', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def sync_offline_movements():
    """
    Bulk sync endpoint to process the offline queue. 
    Resolves items by scanned_code if item_id is missing (Blind Scans).
    """
    payloads = request.get_json() or []
    if not isinstance(payloads, list):
        return jsonify({'error': 'Geçersiz veri formatı. (Invalid format)'}), 400
        
    synced_count = 0
    errors = []
    
    for data in payloads:
        item_id = data.get('item_id')
        scanned_code = data.get('scanned_code')
        mov_type_str = data.get('movement_type', 'IN').upper()
        quantity = float(data.get('quantity', 0.0))
        
        # Resolving Blind Scans: If we only have the barcode, find the item now
        item = None
        if item_id:
            item = db.session.get(Item, item_id)
        elif scanned_code:
            item = db.session.scalar(db.select(Item).filter(
                or_(Item.barcode == scanned_code, Item.qr_code == scanned_code, Item.code == scanned_code)
            ))
            
        if not item:
            errors.append(f"Barkod bulunamadı (Barcode not found): {scanned_code}")
            continue
            
        try:
            movement_type = MovementType[mov_type_str]
        except KeyError:
            continue
            
        # Perform the actual stock math using an internal helper to avoid code duplication
        movement = StockMovement(**{'movement_type': movement_type, 'quantity': quantity, 'scanned_code': scanned_code, 'reference_document': 'OFFLINE_SYNC'})
        item.stock_movements.append(movement)
        item.stock_quantity += quantity if movement_type in [MovementType.IN, MovementType.RETURN, MovementType.ADJUSTMENT] else -quantity
        synced_count += 1

    db.session.commit()
    logger.info(f"Offline Sync Complete: {synced_count} records processed.")
    
    return jsonify({'success': True, 'synced_count': synced_count, 'errors': errors})