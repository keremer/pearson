"""
Flask Routes for Arkhon Platform (AEC & Kelebek Orders)
Fully Integrated with crminaec Data-First Architecture
"""
import logging
import os
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from crminaec.core.models import Order, OrderItem, db
from crminaec.platforms.arkhon.orderparser import KelebekOrderParser

arkhon_bp = Blueprint('arkhon', __name__)
logger = logging.getLogger(__name__)

# ==============================================================================
# 🏢 ARKHON DASHBOARD
# ==============================================================================

@arkhon_bp.route('/')
def index():
    """Arkhon Dashboard / Order Overview"""
    try:
        # Fetch the most recent orders
        recent_orders = db.session.query(Order).order_by(Order.order_id.desc()).limit(10).all()
        total_orders = db.session.query(Order).count()
        total_items = db.session.query(OrderItem).count()
        
        stats = {
            'total_orders': total_orders,
            'total_items': total_items
        }
        
        return render_template('arkhon/arkhon_dashboard.html', orders=recent_orders, stats=stats)
    except Exception as e:
        logger.error(f"Dashboard load error: {e}")
        flash("Could not load dashboard data.", "error")
        return render_template('arkhon/arkhon_dashboard.html', orders=[], stats={})

@arkhon_bp.route('/order/<int:order_id>')
def order_detail(order_id):
    """View details of a specific parsed order"""
    order = db.session.query(Order).filter_by(order_id=order_id).first()
    
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for('arkhon.index'))
        
    return render_template('arkhon/order_detail.html', order=order, items=order.items)


@arkhon_bp.route('/order/<int:order_id>/delete', methods=['POST'])
def delete_order(order_id):
    """Delete an order (Cascade will automatically delete all OrderItems)"""
    try:
        order = db.session.query(Order).filter_by(order_id=order_id).first()
        if order:
            db.session.delete(order)
            db.session.commit()
            flash(f"Order #{order_id} and all its items have been deleted.", "success")
        else:
            flash("Order not found.", "error")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting order: {e}")
        flash("An error occurred while deleting the order.", "error")
        
    return redirect(url_for('arkhon.index'))

# ==============================================================================
# 📥 KELEBEK HTML IMPORT ROUTE
# ==============================================================================

@arkhon_bp.route('/order/import', methods=['GET', 'POST'])
def import_kelebek_order():
    """Handles uploading and parsing of Kelebek Furniture HTML exports"""
    if request.method == 'GET':
        return render_template('arkhon/import_order.html')
        
    if 'file' not in request.files:
        flash('No file part in the request.', 'error')
        return redirect(request.url)
        
    file = request.files['file']
    
    if not file.filename:
        flash('No file selected.', 'error')
        return redirect(request.url)
        
    if not file.filename.endswith('.html'):
        flash('Please upload a valid Kelebek HTML export (.html).', 'error')
        return redirect(request.url)
        
    try:
        # Read the file directly into memory
        html_content = file.read().decode('utf-8', errors='ignore')
        
        # Pass to our robust parser
        parsed_items = KelebekOrderParser.parse_html(html_content)
        
        if not parsed_items:
            flash('No valid products found in the uploaded HTML file. Is it a valid Kelebek export?', 'warning')
            return redirect(request.url)
            
        # 🛠️ THE FIX: Generate a smart order number
        # Example: If file is "Mutfak.html", order number becomes "Mutfak-20260328-1052"
        base_filename = os.path.splitext(secure_filename(file.filename))[0]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        generated_order_number = f"{base_filename}-{timestamp}"
        
        # Create a new Order shell, satisfying the Dataclass requirement
        new_order = Order(order_number=generated_order_number)
        
        # Attach the parsed items to the order
        for item_data in parsed_items:
            # SAFETY FILTER: Only pass keys that actually exist on the OrderItem model.
            safe_data = {k: v for k, v in item_data.items() if hasattr(OrderItem, k)}
            
            order_item = OrderItem(**safe_data)
            new_order.items.append(order_item)
            
        # Commit the transaction
        db.session.add(new_order)
        db.session.commit()
        
        flash(f'Successfully imported order #{new_order.order_number} with {len(parsed_items)} items!', 'success')
        return redirect(url_for('arkhon.order_detail', order_id=new_order.order_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Order Import Failed: {e}")
        flash(f'A system error occurred during import: {str(e)}', 'error')
        return redirect(request.url)