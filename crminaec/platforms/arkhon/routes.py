"""
Flask Routes for Arkhon Platform (AEC & Kelebek Orders)
Fully Integrated with crminaec Data-First Architecture
"""
import logging
import os
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from crminaec.core.models import Order, OrderItem, Quote, CatalogProduct, db
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
    order = db.get_or_404(Order, order_id)
    # Fetch catalog items to populate the Add Appliance dropdown in the UI
    catalog_items = db.session.query(CatalogProduct).all()
        
    return render_template('arkhon/order_detail.html', order=order, items=order.items, catalog_items=catalog_items)


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
        html_content = file.read().decode('utf-8', errors='ignore')
        parsed_items = KelebekOrderParser.parse_html(html_content)
        
        if not parsed_items:
            flash('No valid products found in the uploaded HTML file. Is it a valid Kelebek export?', 'warning')
            return redirect(request.url)
            
        base_filename = os.path.splitext(secure_filename(file.filename))[0]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        generated_order_number = f"{base_filename}-{timestamp}"
        
        new_order = Order(order_number=generated_order_number)
        
        for item_data in parsed_items:
            safe_data = {k: v for k, v in item_data.items() if hasattr(OrderItem, k)}
            order_item = OrderItem(**safe_data)
            new_order.items.append(order_item)
            
        db.session.add(new_order)
        db.session.commit()
        
        flash(f'Successfully imported order #{new_order.order_number} with {len(parsed_items)} items!', 'success')
        return redirect(url_for('arkhon.order_detail', order_id=new_order.order_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Order Import Failed: {e}")
        flash(f'A system error occurred during import: {str(e)}', 'error')
        return redirect(request.url)


# ==============================================================================
# 🛠️ QUOTE BUILDING & CATALOG ROUTING
# ==============================================================================

@arkhon_bp.route('/order/<int:order_id>/add_catalog_item', methods=['POST'])
def add_catalog_item(order_id):
    """Adds a standard catalog product (Appliance/Countertop) to an order."""
    order = db.get_or_404(Order, order_id)
    product_id = request.form.get('catalog_product_id')
    qty = float(request.form.get('qty', 1.0))
    
    if product_id:
        product = db.session.query(CatalogProduct).get(product_id)
        if product:
            new_item = OrderItem(
                urk=product.product_code,
                ura=f"{product.brand} - {product.product_name}",
                adet=qty,
                brm="adet",
                category=product.category,
                is_visible_on_quote=True,
                accessory_image_path=product.image_url
            )
            order.items.append(new_item)
            db.session.commit()
            flash(f'Added {product.product_name} to the order.', 'success')
        else:
            flash('Product not found in catalog.', 'danger')
            
    return redirect(url_for('arkhon.order_detail', order_id=order_id))


@arkhon_bp.route('/order/<int:order_id>/quote/build', methods=['GET', 'POST'])
def build_quote(order_id):
    """Internal UI to set ProSAP pricing, hide margin items, and generate a Quote."""
    order = db.get_or_404(Order, order_id)
    
    if request.method == 'POST':
        try:
            for item in order.items:
                is_visible = request.form.get(f'visibility_{item.item_id}') == 'on'
                category = request.form.get(f'category_{item.item_id}', 'Furniture')
                
                item.is_visible_on_quote = is_visible
                item.category = category

            list_price = float(request.form.get('list_price', 0))
            discount = float(request.form.get('discount_amount', 0))
            tax_rate = float(request.form.get('tax_rate', 20.0))
            total_amount = float(request.form.get('total_amount', 0))

            current_quotes = db.session.query(Quote).filter_by(order_id=order.order_id).count()
            next_version = current_quotes + 1

            new_quote = Quote(
                version=next_version,
                list_price=list_price,
                discount_amount=discount,
                tax_rate=tax_rate,
                total_amount=total_amount,
                validity_days=int(request.form.get('validity_days', 15)),
                payment_terms=request.form.get('payment_terms', ''),
                delivery_place=request.form.get('delivery_place', ''),
                special_notes=request.form.get('special_notes', '')
            )
            
            order.quotes.append(new_quote)
            db.session.commit()
            
            flash(f'Quote Version {next_version} generated successfully!', 'success')
            return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error generating quote: {str(e)}', 'danger')

    return render_template('arkhon/quote_builder.html', order=order)

@arkhon_bp.route('/order/<int:order_id>/ghost-summary')
def ghost_summary(order_id):
    """Generates the lean, unbranded totals page for negotiation."""
    order = db.get_or_404(Order, order_id)
    return render_template('arkhon/ghost_summary.html', order=order, current_date=datetime.now().strftime('%Y-%m-%d'))


# ==============================================================================
# 🤝 PUBLIC CLIENT PORTAL (No Auth Required, Token Based)
# ==============================================================================

@arkhon_bp.route('/quote/p/<access_token>', methods=['GET'])
def public_quote(access_token):
    """The secure, public-facing portal for the client to view their quote."""
    quote = db.first_or_404(db.select(Quote).filter_by(access_token=access_token))
    order = quote.order
    
    visible_items = [item for item in order.items if item.is_visible_on_quote]
    
    return render_template(
        'arkhon/public_quote.html', 
        quote=quote, 
        order=order, 
        visible_items=visible_items
    )

@arkhon_bp.route('/quote/p/<access_token>/approve', methods=['POST'])
def approve_quote(access_token):
    """Processes the legal e-signature and captures the IP."""
    quote = db.first_or_404(db.select(Quote).filter_by(access_token=access_token))
        
    if quote.status == 'approved':
        flash('This quote is already approved.', 'info')
        return redirect(url_for('arkhon.public_quote', access_token=access_token))

    approval_text = request.form.get('approval_text', '').strip()
    expected_text = "I have read and approve this quote and its terms." 
    
    if approval_text.lower() != expected_text.lower():
        flash('Approval text does not match. Please type the exact phrase to legally approve.', 'danger')
        return redirect(url_for('arkhon.public_quote', access_token=access_token))

    try:
        quote.status = 'approved'
        quote.approval_text = approval_text
        quote.approval_date = datetime.utcnow()
        quote.approval_ip = request.remote_addr or 'Unknown IP' 
        
        db.session.commit()
        flash('Quote successfully approved! Your contract is being prepared.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while saving your approval.', 'danger')
        
    return redirect(url_for('arkhon.public_quote', access_token=access_token))