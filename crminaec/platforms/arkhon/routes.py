"""
Flask Routes for Arkhon Platform (AEC & Kelebek Orders)
Fully Integrated with crminaec Data-First Architecture
"""
import csv
import io
import logging
import os
from datetime import datetime, timedelta

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)
from werkzeug.utils import secure_filename

from crminaec.core.interop.manager import Platform, create_interop_manager
from crminaec.core.models import (CatalogProduct, Order, OrderItem, Party,
                                  PaymentInstallment, PriceRecord,
                                  ProjectPreference, Quote, db)
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
        parsed_data = KelebekOrderParser.parse_html(html_content)
        
        # Handle dictionary structure
        parsed_items = parsed_data.get('items', [])
        cust_info = parsed_data.get('customer', {})

        if not parsed_items:
            flash('No valid products found in the uploaded HTML file. Is it a valid Kelebek export?', 'warning')
            return redirect(request.url)
            
        base_filename = os.path.splitext(secure_filename(file.filename))[0]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        generated_order_number = f"{base_filename}-{timestamp}"
        
        # Only pass valid Order fields to constructor
        new_order = Order(order_number=generated_order_number)
        
        for item_data in parsed_items:
            safe_data = {k: v for k, v in item_data.items() if hasattr(OrderItem, k)}
            order_item = OrderItem(**safe_data)
            new_order.items.append(order_item)
            
        # --- AUTO-LINK CUSTOMER PARTY ---
        email = cust_info.get('email', '')
        first_name = cust_info.get('first_name', '')
        last_name = cust_info.get('last_name', '')
        
        if email or first_name or last_name:
            party = db.session.query(Party).filter_by(email=email).first() if email else None
            if not party:
                party = Party(
                    email=email if email else f"temp_{timestamp}@crminaec.local",
                    first_name=first_name,
                    last_name=last_name
                )
                db.session.add(party)
                db.session.flush()
            
            # Attach phone and address if model supports it
            if hasattr(party, 'phone') and cust_info.get('phone'):
                party.phone = cust_info.get('phone')
            if hasattr(party, 'address') and cust_info.get('address'):
                party.address = cust_info.get('address')
                
            new_order.party_id = party.party_id

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
# 📥 PROSAP CSV IMPORT ROUTE
# ==============================================================================
@arkhon_bp.route('/order/<int:order_id>/import_prosap_csv', methods=['POST'])
def import_prosap_csv(order_id):
    """Reads a ProSAP CSV and injects prices into the Order's PriceRecords."""
    order = db.get_or_404(Order, order_id)
    
    # --- STRICT PREFERENCE VALIDATION GATE ---
    prefs = order.preferences
    if not prefs:
        flash('Lütfen teklif oluşturmadan önce Sipariş Tercihlerini (Müşteri, Renk, Kulp vb.) onaylayıp kaydedin.', 'warning')
        return redirect(url_for('arkhon.order_preferences', order_id=order.order_id))
        
    missing_fields = []
    if not order.party or not order.party.first_name or not order.party.last_name:
        missing_fields.append("Müşteri Adı ve Soyadı")
    if not prefs.model_name: missing_fields.append("Kapak Modeli")
    if not prefs.front_color: missing_fields.append("Kapak Rengi")
    if not prefs.body_color: missing_fields.append("Gövde Rengi")
    if not prefs.plinth_detail: missing_fields.append("Baza Yüksekliği/Rengi")
    if not prefs.handle_code: missing_fields.append("Kulp Kodu/Modeli")
    
    if missing_fields:
        flash(f'Teklif oluşturmadan önce şu bilgilerin eksiksiz olması gereklidir: {", ".join(missing_fields)}', 'warning')
        return redirect(url_for('arkhon.order_preferences', order_id=order.order_id))
    
    if 'prosap_file' not in request.files:
        flash('Lütfen bir CSV dosyası seçin.', 'warning')
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
        
    file = request.files['prosap_file']
    if file.filename == '':
        flash('Dosya seçilmedi.', 'warning')
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

    try:
        # 1. Read the CSV File (Decoding it to string)
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        
        # NOTE: Adjust delimiter to ';' if ProSAP uses semicolons for Turkish Excel formatting!
        csv_input = csv.DictReader(stream, delimiter=',') 
        
        # 2. Convert CSV rows into a fast lookup dictionary: { 'URK_CODE': 12500.00 }
        # You will need to change 'Ünite Kodu' and 'Fiyat' to match the exact column headers in the ProSAP CSV
        prosap_prices = {}
        for row in csv_input:
            unit_code = row.get('Ünite Kodu', '').strip()
            raw_price = row.get('Fiyat', '0').replace('.', '').replace(',', '.') # Handle Turkish number format
            
            if unit_code:
                prosap_prices[unit_code] = float(raw_price)

        # 3. Match and Update the Database
        updated_count = 0
        for item in order.items:
            # If the item has a code AND it exists in our CSV lookup
            if item.urk and item.urk in prosap_prices:
                new_price_val = prosap_prices[item.urk]
                
                # Create a new historical PriceRecord
                new_price_record = PriceRecord(**{
                    'entity_code': item.urk or "BİLİNMEYEN",
                    'supplier': "Kelebek (ProSAP)",
                    'price_type': "cost",
                    'base_material_cost': new_price_val,
                    'final_unit_price': new_price_val 
                })
                db.session.add(new_price_record)
                
                # Link the item to this new price record
                item.price_record = new_price_record
                updated_count += 1

        db.session.commit()
        flash(f'{updated_count} kalemin fiyatı ProSAP CSV dosyasından başarıyla güncellendi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"ProSAP CSV Import Failed: {e}")
        flash(f'CSV yüklenirken bir hata oluştu: {str(e)}', 'danger')

    return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

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
            new_item = OrderItem(**{
                'urk': product.product_code,
                'ura': f"{product.brand} - {product.product_name}",
                'adet': qty,
                'brm': "adet",
                'category': product.category,
                'is_visible_on_quote': True,
                'accessory_image_path': product.image_url
            })
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
    
    # Check if we are editing or duplicating an existing quote
    source_quote_id = request.args.get('source', type=int)
    edit_quote_id = request.args.get('edit', type=int)
    
    quote_to_load = None
    is_edit_mode = False
    
    if edit_quote_id:
        quote_to_load = db.session.query(Quote).filter_by(quote_id=edit_quote_id, order_id=order.order_id).first()
        is_edit_mode = True
    elif source_quote_id:
        quote_to_load = db.session.query(Quote).filter_by(quote_id=source_quote_id, order_id=order.order_id).first()

    if request.method == 'POST':
        try:
            # ... (Keep your existing visibility and category loop here) ...
            for item in order.items:
                is_visible = request.form.get(f'visibility_{item.item_id}') == 'on'
                category = request.form.get(f'category_{item.item_id}', 'Furniture')
                item.is_visible_on_quote = is_visible
                item.category = category

            list_price = float(request.form.get('list_price', 0))
            discount = float(request.form.get('discount_amount', 0))
            tax_rate = float(request.form.get('tax_rate', 20.0))
            total_amount = float(request.form.get('total_amount', 0))
            validity_days = int(request.form.get('validity_days', 15))
            payment_terms = request.form.get('payment_terms', '')
            delivery_place = request.form.get('delivery_place', '')
            special_notes = request.form.get('special_notes', '')

            if is_edit_mode and quote_to_load:
                # Update existing quote in place
                quote_to_load.list_price = list_price
                quote_to_load.discount_amount = discount
                quote_to_load.tax_rate = tax_rate
                quote_to_load.total_amount = total_amount
                quote_to_load.validity_days = validity_days
                quote_to_load.payment_terms = payment_terms
                quote_to_load.delivery_place = delivery_place
                quote_to_load.special_notes = special_notes
                
                # Clear out old installments to cleanly replace them
                for inst in quote_to_load.installments:
                    db.session.delete(inst)
                    
                target_quote = quote_to_load
                flash_msg = f'Teklif Versiyon {quote_to_load.version} başarıyla güncellendi!'
            else:
                # Create a brand new version
                current_quotes = db.session.query(Quote).filter_by(order_id=order.order_id).count()
                next_version = current_quotes + 1

                target_quote = Quote(**{
                    'version': next_version,
                    'list_price': list_price,
                    'discount_amount': discount,
                    'tax_rate': tax_rate,
                    'total_amount': total_amount,
                    'validity_days': validity_days,
                    'payment_terms': payment_terms,
                    'delivery_place': delivery_place,
                    'special_notes': special_notes
                })
                order.quotes.append(target_quote)
                flash_msg = f'Teklif Versiyon {next_version} başarıyla oluşturuldu!'
            
            # ==========================================
            # 🛑 NEW: PROCESS DYNAMIC PAYMENT INSTALLMENTS
            # ==========================================
            dates = request.form.getlist('installment_date[]')
            methods = request.form.getlist('installment_method[]')
            amounts = request.form.getlist('installment_amount[]')
            
            # Zip them together and create the database records
            for date_str, method, amount_str in zip(dates, methods, amounts):
                if method and amount_str: # Only add if method and amount exist
                    amount_val = float(amount_str)
                    # Convert date string to datetime if provided, else leave None
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else None
                    
                    installment = PaymentInstallment(**{
                        'date': parsed_date,
                        'method': method,
                        'amount': amount_val,
                        'status': "Bekliyor"
                    })
                    target_quote.installments.append(installment)
            
            db.session.commit()
            
            flash(flash_msg, 'success')
            return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Teklif oluşturulurken hata: {str(e)}', 'danger')

    return render_template('arkhon/quote_builder.html', order=order, source_quote=quote_to_load, is_edit_mode=is_edit_mode)

@arkhon_bp.route('/quote/<int:quote_id>/archive', methods=['POST'])
def archive_quote(quote_id):
    """Marks a quote as archived so it is hidden from the main active list."""
    quote = db.get_or_404(Quote, quote_id)
    try:
        quote.status = 'archived'
        db.session.commit()
        flash(f'Teklif v{quote.version} arşive kaldırıldı.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Arşive kaldırma sırasında hata: {str(e)}', 'danger')
    return redirect(url_for('arkhon.order_detail', order_id=quote.order_id))

@arkhon_bp.route('/quote/<int:quote_id>/email', methods=['POST'])
def email_quote(quote_id):
    """Sends the quote link to the customer via Email."""
    quote = db.get_or_404(Quote, quote_id)
    order = quote.order
    
    if not order.party or not order.party.email:
        flash("Müşterinin e-posta adresi kayıtlı değil. Lütfen 'Tercihler' kısmından ekleyin.", "warning")
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
        
    try:
        from flask_mail import Message

        from crminaec import mail
        
        portal_url = url_for('arkhon.public_quote', access_token=quote.access_token, _external=True)
        customer_name = order.party.first_name or "Değerli Müşterimiz"
        
        msg = Message(
            subject=f"Arkhon Mimarlık - {quote.quote_category} Teklifiniz (v{quote.version})",
            recipients=[order.party.email],
            body=f"Merhaba {customer_name},\n\n{quote.quote_category} teklifinizi (Versiyon {quote.version}) incelemek ve dijital olarak onaylamak için aşağıdaki bağlantıya tıklayabilirsiniz:\n\n{portal_url}\n\nSaygılarımızla,\nArkhon Mimarlık",
        )
        sender = current_app.config.get('MAIL_DEFAULT_SENDER')
        if sender:
            msg.sender = sender
            
        mail.send(msg)
        flash(f"Teklif bağlantısı başarıyla {order.party.email} adresine gönderildi.", "success")
    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        flash(f"E-posta gönderilirken bir hata oluştu: {str(e)}", "danger")
        
    return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

@arkhon_bp.route('/order/<int:order_id>/ghost_summary')
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
    expected_text = "Okudum anladım onaylıyorum" 
    
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

@arkhon_bp.route('/order/<int:order_id>/preferences', methods=['GET', 'POST'])
def order_preferences(order_id):
    """Turkish UI for Müşteri ve Sipariş Takip Formu with Auto-Extraction."""
    order = db.get_or_404(Order, order_id)
    
    # 1. AUTO-EXTRACTION ENGINE (Runs if preferences don't exist, OR if user forces a rebuild)
    rebuild = request.args.get('rebuild', type=int) == 1
    
    if not order.preferences or rebuild:
        prefs = order.preferences if order.preferences else ProjectPreference()
        
        if rebuild:
            prefs.model_name = None
            prefs.body_color = None
            prefs.front_color = None
            prefs.handle_code = None
            prefs.plinth_detail = None
            prefs.cutlery_tray = None
            prefs.trash_bin = None
            prefs.mechanisms = None
            prefs.glass_color = None
            prefs.led_strip = False
            prefs.spotlight = False
            
        mechanisms_list = []
        
        for item in order.items:
            name_lower = (item.ura or "").lower()
            
            # Extract Global Model & Colors
            if not prefs.model_name and hasattr(item, 'oza') and item.oza and item.oza.strip() != "-":
                code_str = f" ({item.ozk.strip()})" if hasattr(item, 'ozk') and item.ozk and item.ozk.strip() not in ["", "-"] else ""
                prefs.model_name = f"{item.oza.strip()}{code_str}"
                
            if not prefs.body_color and hasattr(item, 'govderna') and item.govderna and item.govderna.strip() != "-":
                code_str = f" ({item.govdernk.strip()})" if hasattr(item, 'govdernk') and item.govdernk and item.govdernk.strip() not in ["", "-"] else ""
                prefs.body_color = f"{item.govderna.strip()}{code_str}"
                
            if not prefs.front_color and hasattr(item, 'rna') and item.rna and item.rna.strip() != "-":
                code_str = f" ({item.rnk.strip()})" if hasattr(item, 'rnk') and item.rnk and item.rnk.strip() not in ["", "-"] else ""
                prefs.front_color = f"{item.rna.strip()}{code_str}"
                
            # Extract Handle (Kulp) - Kelebek handles usually start with YH in URK
            if "kulp" in name_lower or (item.urk and str(item.urk).startswith("YH")):
                if not prefs.handle_code:
                    prefs.handle_code = item.ura
                    
            # Extract Plinth (Baza/Tamel) - Kelebek plinths usually start with M7600
            if "tamel" in name_lower or "baza" in name_lower or (item.urk and "M7600" in str(item.urk)):
                if not prefs.plinth_detail:
                    prefs.plinth_detail = "12cm Baza" if "05" in str(item.urk) else "15cm Baza"
                
            # Extract Accessories & Mechanisms
            if "kaşıklık" in name_lower or "kasiklik" in name_lower or "kaşıklığı" in name_lower:
                if not prefs.cutlery_tray:
                    prefs.cutlery_tray = item.ura
            if "çöp" in name_lower or "cop" in name_lower:
                if not prefs.trash_bin:
                    prefs.trash_bin = item.ura
                
            if any(x in name_lower for x in ["kiler", "kör köşe", "mekanizma", "şişelik", "siselik", "fasulye", "le mans"]):
                mechanisms_list.append(item.ura)
                
            # Extract Glass
            if "cam" in name_lower and not prefs.glass_color:
                prefs.glass_color = item.ura
                
            # Extract Lighting
            if "led" in name_lower or "aydınlatma" in name_lower:
                prefs.led_strip = True
            if "spot" in name_lower:
                prefs.spotlight = True

        if mechanisms_list:
            # Deduplicate and join multiple mechanisms neatly
            prefs.mechanisms = " \n".join(list(set(mechanisms_list)))
            
        if not order.preferences:
            order.preferences = prefs
            
        db.session.commit()
        
        if rebuild:
            flash('Tercihler Kelebek verilerinden yeniden çekilerek güncellendi!', 'success')
            return redirect(url_for('arkhon.order_preferences', order_id=order.order_id))
        else:
            flash('Tercihler Kelebek sipariş verilerinden otomatik olarak ayıklandı!', 'success')

    # 2. HANDLE FORM SUBMISSION (Updating the values manually)
    if request.method == 'POST':
        try:
            # --- 1. PROCESS CUSTOMER INFO (Party Linking & Updates) ---
            cust_first = request.form.get('customer_first_name', '').strip()
            cust_last = request.form.get('customer_last_name', '').strip()
            cust_email = request.form.get('customer_email', '').strip()
            cust_phone = request.form.get('customer_phone', '').strip()
            cust_address = request.form.get('customer_address', '').strip()
            
            if cust_first or cust_email:
                # Find existing by email, or use the currently linked party
                party = db.session.query(Party).filter_by(email=cust_email).first() if cust_email else None
                
                if not party and order.party:
                    party = order.party
                elif not party:
                    party = Party(**{'email': cust_email})
                    db.session.add(party)
                    
                party.first_name = cust_first
                party.last_name = cust_last
                if cust_email: party.email = cust_email
                if hasattr(party, 'phone'): party.phone = cust_phone
                if hasattr(party, 'address'): party.address = cust_address
                    
                order.party = party

            # --- 2. PROCESS PREFERENCES ---
            order.preferences.model_name = request.form.get('model_name')
            order.preferences.front_color = request.form.get('front_color')
            order.preferences.body_color = request.form.get('body_color')
            order.preferences.plinth_detail = request.form.get('plinth_detail')
            order.preferences.handle_code = request.form.get('handle_code')
            order.preferences.glass_color = request.form.get('glass_color')
            
            # Checkboxes
            order.preferences.led_strip = request.form.get('led_strip') == 'on'
            order.preferences.spotlight = request.form.get('spotlight') == 'on'
            
            order.preferences.cutlery_tray = request.form.get('cutlery_tray')
            order.preferences.trash_bin = request.form.get('trash_bin')
            order.preferences.mechanisms = request.form.get('mechanisms')

            db.session.commit()
            flash('Sipariş tercihleri başarıyla güncellendi.', 'success')
            return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'danger')

    return render_template('arkhon/preferences_form.html', order=order)

logger = logging.getLogger(__name__)

# --- Helper Function for Turkish Currency Formatting ---
def format_try(amount):
    """Formats a float to Turkish Lira string: 1.234.567,89"""
    if amount is None:
        amount = 0.0
    formatted = f"{amount:,.2f}"
    return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')

@arkhon_bp.route('/quote/<int:quote_id>/export/gdoc', methods=['POST'])
def export_quote_gdoc(quote_id):
    """Gathers B2B project quote data and sends it to Google Docs."""
    quote = db.get_or_404(Quote, quote_id)
    order = quote.order
    
    try:
        # 1. Prepare Customer & Project Meta Data
        customer_fullname = (f"{order.party.first_name or ''} {order.party.last_name or ''}".strip() or "Müşteri") if order.party else "Müşteri"
        project_name = getattr(order, 'project_name', 'Konut Projesi')
        validity_date_str = (datetime.now() + timedelta(days=quote.validity_days)).strftime('%d.%m.%Y')
        
        total_kitchen_count = 0
        typology_list_bulleted = ""
        project_summary_table = []
        typology_itemized_pages = []
        grand_total = 0.0
        
        # Determine Kitchen Model Name dynamically
        model_name = "Standart Mutfak"
        if order.preferences and order.preferences.model_name:
            model_name = order.preferences.model_name
        else:
            for item in order.items:
                if hasattr(item, 'oza') and item.oza and item.oza.strip() and item.oza.strip() != '-':
                    code_str = f" ({item.ozk.strip()})" if hasattr(item, 'ozk') and item.ozk and item.ozk.strip() not in ["", "-"] else ""
                    model_name = f"{item.oza.strip()}{code_str}"
                    break
        
        # 2. B2B Typology Logic with ERP Pricing
        if hasattr(order, 'typologies') and order.typologies:
            for typo in order.typologies:
                total_kitchen_count += typo.quantity
                typology_list_bulleted += f"• {typo.name} MUTFAK ({typo.description}) - {typo.quantity} ADET\n"
                
                visible_items = [item for item in typo.items if item.is_visible_on_quote]
                
                unit_cost = 0.0
                for item in visible_items:
                    if item.price_record and item.price_record.final_unit_price is not None:
                        unit_cost += float(item.price_record.final_unit_price)

                row_total = unit_cost * typo.quantity
                grand_total += row_total
                
                project_summary_table.append({
                    "MUTFAK TİPİ": f"{typo.name} ({typo.description})",
                    "ADET FİYATI": format_try(unit_cost),
                    "TOPLAM FİYAT": format_try(row_total)
                })
                
                typology_itemized_pages.append({
                    "typology_name": typo.name,
                    "items": [{"name": i.ura, "code": i.urk, "qty": i.adet, "unit": i.brm} for i in visible_items]
                })
                
            project_summary_table.append({
                "MUTFAK TİPİ": "TOPLAM",
                "ADET FİYATI": "",
                "TOPLAM FİYAT": format_try(grand_total)
            })
            
        else:
            total_kitchen_count = 1
            visible_items = [item for item in order.items if item.is_visible_on_quote]
            
            project_summary_table.append({
                "MUTFAK TİPİ": model_name,
                "ADET FİYATI": format_try(quote.total_amount),
                "TOPLAM FİYAT": format_try(quote.total_amount)
            })
            typology_itemized_pages.append({
                "typology_name": model_name,
                "items": [{"name": i.ura, "code": i.urk, "qty": i.adet, "unit": i.brm} for i in visible_items]
            })

        # 3. Format the tables into clean strings for the Google Doc
        summary_text = ""
        for row in project_summary_table:
            if row.get("MUTFAK TİPİ") == "TOPLAM":
                summary_text += f"\nGENEL TOPLAM: {row.get('TOPLAM FİYAT')} ₺\n"
            else:
                summary_text += f"• {row.get('MUTFAK TİPİ')} : {row.get('TOPLAM FİYAT')} ₺\n"

        itemized_text = ""
        for page in typology_itemized_pages:
            itemized_text += f"\n--- {page['typology_name']} MUTFAK ÜNİTELERİ ---\n"
            for item in page['items']:
                itemized_text += f"• [{item['code']}] {item['name']} - {item['qty']} {item['unit']}\n"

        # 3.5 Build the Installment Breakdown Table
        installment_text = ""
        if quote.installments:
            for inst in quote.installments:
                date_str = inst.date.strftime('%d.%m.%Y') if inst.date else "Belirtilmedi"
                installment_text += f"• {date_str}  |  {inst.method}  |  {format_try(inst.amount)} ₺\n"
        else:
            installment_text = "Özel bir ödeme planı belirtilmemiştir."

        # 4. Build the Replacement Dictionary (Tag -> Value)
        replacements = [
            {'{{quote_number}}': f"{order.order_number}-V{quote.version}"},
            {'{{date}}': datetime.now().strftime('%d.%m.%Y')},
            {'{{customer_name}}': customer_fullname},
            {'{{project_name}}': project_name},
            {'{{total_kitchen_count}}': str(total_kitchen_count)},
            {'{{typology_list_bulleted}}': typology_list_bulleted.strip()},
            {'{{project_summary_table}}': summary_text},
            {'{{typology_itemized_pages}}': itemized_text},
            {'{{installment_plan_table}}': installment_text},
            {'{{payment_terms}}': quote.payment_terms or "Ödeme planı ektedir."},
            {'{{validity_date}}': validity_date_str}
        ]
        
        # 5. Initialize the Universal Manager
        interop = create_interop_manager()
        gdocs_client = interop.clients.get(Platform.GOOGLE_DOCS)
        
        # PYLANCE LEAK 1: If client doesn't exist, we MUST return a redirect!
        if not gdocs_client:
            flash("Google Docs platform is not enabled or failed to initialize.", "danger")
            return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

        TEMPLATE_ID = "1X1VEL2p54n2BIrcWslEmbiyV24KmL4XVy0JWBVAJfnQ" 
        FOLDER_ID = "1WH9vQuJVEvKEFYK4vi-np3KSDhp2o8jT"
        NEW_TITLE = f"Teklif_{order.order_number}_{customer_fullname}"
        
        # 6. Generate!
        if hasattr(gdocs_client, 'generate_from_template'):
            new_doc_id = gdocs_client.generate_from_template( # type: ignore
                template_id=TEMPLATE_ID,
                title=NEW_TITLE,
                replacements=replacements,
                folder_id=FOLDER_ID
            )
            
            if new_doc_id:
                gdoc_url = f"https://docs.google.com/document/d/{new_doc_id}/edit"
                # Instantly redirect the new tab directly to the Google Doc
                return redirect(gdoc_url)
            else:
                flash('Google Docs API reddetti. Konsol loglarını kontrol edin.', 'danger')
        else:
            flash("The selected client does not support template generation.", "danger")
            
        # PYLANCE LEAK 2: The successful try block MUST return a redirect!
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
        
    except Exception as e:
        logger.error(f"Google Docs Export Failed: {e}")
        flash(f'Google Docs oluşturulurken bir hata oluştu: {str(e)}', 'danger')
        # PYLANCE LEAK 3: The exception block MUST return a redirect!
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
    