"""
Flask Routes for Arkhon Platform (AEC & Kelebek Orders)
Fully Integrated with crminaec Data-First Architecture
"""
import csv
import io
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from crminaec.core.interop.manager import Platform, create_interop_manager
from crminaec.core.models import (CatalogProduct, CustomerIssue, Order,
                                  OrderAttachment, OrderItem, Party,
                                  PaymentInstallment, PriceRecord,
                                  ProjectPreference, Quote, db)
from crminaec.core.security import role_required
from crminaec.platforms.arkhon.orderparser import KelebekOrderParser

arkhon_bp = Blueprint('arkhon', __name__)
logger = logging.getLogger(__name__)

# ==============================================================================
# 🚀 LEAD MANAGEMENT & PRE-SALES WORKFLOW
# ==============================================================================

@arkhon_bp.route('/lead/new', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def create_lead():
    """Creates a new customer lead from a store visit."""
    party_id = request.form.get('party_id')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    project_type = request.form.get('project_type', 'Kitchen')
    meas_date_str = request.form.get('measurement_date')
    
    measurement_date = None
    if meas_date_str:
        try:
            measurement_date = datetime.strptime(meas_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
    
    party = None
    if party_id:
        party = db.session.get(Party, party_id)
        
    # Reliable Tracking: Fallback to find Party by email OR phone couple
    if not party and email:
        party = db.session.scalar(db.select(Party).filter_by(email=email))
    if not party and phone:
        party = db.session.scalar(db.select(Party).filter_by(phone=phone))
        
    if not party:
        party = Party(**{
            'email': email if email else f"lead_{datetime.now().strftime('%Y%m%d%H%M')}@crminaec.local",
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'address': address
        })
        db.session.add(party)
        db.session.flush()
    else:
        # Update missing info cleanly
        if not party.phone and phone: party.phone = phone
        if not party.address and address: party.address = address
        if not party.first_name and first_name: party.first_name = first_name
        if not party.last_name and last_name: party.last_name = last_name
        
    order_number = f"LD-{datetime.now().strftime('%Y%m%d-%H%M')}"
    new_order = Order(**{
        'order_number': order_number,
        'party_id': party.party_id,
        'party': party,
        'status': 'lead',
        'project_type': project_type,
        'measurement_date': measurement_date
    })
    db.session.add(new_order)
    db.session.commit()
    
    flash(f"Yeni müşteri talebi başarıyla oluşturuldu: {order_number}", "success")
    return redirect(url_for('arkhon.order_detail', order_id=new_order.order_id))

@arkhon_bp.route('/order/<int:order_id>/send_kvkk', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def send_kvkk_link(order_id):
    """Sends the registration/KVKK link to the customer via Email."""
    order = db.get_or_404(Order, order_id)
    if not order.party or not order.party.email or '@crminaec.local' in order.party.email:
        flash("Müşterinin geçerli bir e-posta adresi bulunmuyor.", "warning")
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
        
    try:
        from flask_mail import Message

        from crminaec import mail
        
        reg_url = url_for('auth.register', _external=True)
        msg = Message(
            subject="Arkhon Mimarlık - Portal Kaydı ve KVKK Onayı",
            recipients=[order.party.email],
            body=f"Merhaba {order.party.first_name or ''},\n\nMağazamızı ziyaret ettiğiniz için teşekkür ederiz. Arkhon Mimarlık portalına kayıt olmak ve KVKK aydınlatma metnini onaylamak için aşağıdaki bağlantıya tıklayabilirsiniz:\n\n{reg_url}\n\nSaygılarımızla,\nArkhon Mimarlık"
        )
        sender = current_app.config.get('MAIL_DEFAULT_SENDER')
        if sender: msg.sender = sender
        mail.send(msg)
        flash("KVKK ve Kayıt linki müşteriye başarıyla gönderildi.", "success")
    except Exception as e:
        flash(f"E-posta gönderilemedi: {e}", "danger")
    return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

@arkhon_bp.route('/order/<int:order_id>/log_info_docs', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def log_info_docs(order_id):
    """Logs that manual procedure documents were sent."""
    order = db.get_or_404(Order, order_id)
    order.info_docs_sent = True
    order.info_docs_sent_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Bilgilendirme dokümanları iletildi olarak işaretlendi.", "success")
    return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

@arkhon_bp.route('/order/<int:order_id>/upload_attachment', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def upload_order_attachment(order_id):
    """Uploads a measurement/contract file and auto-renames via strict semantic rules."""
    order = db.get_or_404(Order, order_id)
    if 'file' not in request.files or not request.files['file'].filename:
        flash("Dosya seçilmedi.", "warning")
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
        
    file = request.files['file']
    context = request.form.get('context', 'Measurement')
    
    # Apply Strict Naming Convention (KMEON2604220630_Context)
    fn = (order.party.first_name if order.party and order.party.first_name else 'XX').upper().strip()
    ln = (order.party.last_name if order.party and order.party.last_name else 'XXX').upper().strip()
    
    n_first = fn[0] if len(fn) > 0 else 'X'
    n_last = fn[-1] if len(fn) > 1 else (fn[0] if len(fn) > 0 else 'X')
    
    s_first = ln[0] if len(ln) > 0 else 'X'
    s_last = ln[-1] if len(ln) > 1 else (ln[0] if len(ln) > 0 else 'X')
    s_mid = ln[len(ln)//2] if len(ln) > 2 else 'X'
    
    date_str = datetime.now().strftime("%y%m%d%H%M")
    ext = os.path.splitext(str(file.filename))[1].lower()
    safe_context = re.sub(r'[^\w\s-]', '', context).strip().replace(' ', '_')
    
    semantic_filename = f"{n_first}{n_last}{s_first}{s_mid}{s_last}{date_str}_{safe_context}{ext}"
    
    upload_folder = os.path.join('crminaec', 'static', 'uploads', 'orders')
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, semantic_filename)
    file.save(file_path)
    
    file_type = "image" if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'] else "document"
    db_path = f"/static/uploads/orders/{semantic_filename}"
    
    new_attachment = OrderAttachment(**{
        'original_filename': str(file.filename),
        'semantic_filename': semantic_filename,
        'file_path': db_path,
        'file_type': file_type,
        'context': context
    }) # type: ignore
    order.attachments.append(new_attachment)
    db.session.commit()
    
    flash(f"Dosya yüklendi ve otomatik olarak {semantic_filename} adını aldı.", "success")
    return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

@arkhon_bp.route('/customer/<int:party_id>')
@login_required
def customer_detail(party_id):
    """Customer 360 Profile: Shows tree view of all their leads, orders, and documents."""
    # OWNERSHIP GATE: Customers can only see their own profile
    if current_user.account.role not in ['admin', 'power_user'] and current_user.party_id != party_id:
        abort(403)
        
    party = db.get_or_404(Party, party_id)
    
    # --- TIMELINE AGGREGATION ---
    events = []
    for order in party.orders:
        # 1. Order Creation
        events.append({
            'date': order.date,
            'icon': 'fa-user-clock' if order.status == 'lead' else 'fa-file-import',
            'title': f"Yeni {'Keşif Talebi' if order.status == 'lead' else 'Proje Başlatıldı'} ({order.order_number})",
            'desc': f"İlgi Alanı: {order.project_type}",
            'color': 'primary' if order.status == 'lead' else 'secondary'
        })
        
        # 2. Measurement Appointment
        if order.measurement_date:
            events.append({
                'date': order.measurement_date,
                'icon': 'fa-ruler-combined',
                'title': f"Ölçü / Keşif Randevusu ({order.order_number})",
                'desc': "Saha ziyareti ve ölçüm planlandı.",
                'color': 'info'
            })
            
        # 3. Informational Documents Sent
        if order.info_docs_sent_at:
            events.append({
                'date': order.info_docs_sent_at,
                'icon': 'fa-info-circle',
                'title': f"Bilgilendirme İletildi ({order.order_number})",
                'desc': "Süreç prosedürleri müşteriye gönderildi.",
                'color': 'warning'
            })
            
        # 4. Digital Approvals
        for quote in order.quotes:
            if quote.approval_date:
                events.append({
                    'date': quote.approval_date,
                    'icon': 'fa-signature',
                    'title': f"Sözleşme Onaylandı (v{quote.version})",
                    'desc': f"Kategori: {quote.quote_category} | Dijital IP: {quote.approval_ip or 'Bilinmiyor'}",
                    'color': 'success'
                })
                
        # 4.5. Post-Sales / Installation Milestones
        if order.factory_delivery_date:
            events.append({
                'date': order.factory_delivery_date,
                'icon': 'fa-truck',
                'title': f"Fabrika/Depo Teslimi ({order.order_number})",
                'desc': "Ürünler üretimden çıkıp depoya ulaştı.",
                'color': 'info'
            })
        if order.installation_appointment_date:
            events.append({
                'date': order.installation_appointment_date,
                'icon': 'fa-calendar-check',
                'title': f"Montaj Randevusu ({order.order_number})",
                'desc': "Montaj ekipleri için planlama yapıldı.",
                'color': 'primary'
            })
        if order.kitchen_installation_date:
            events.append({
                'date': order.kitchen_installation_date,
                'icon': 'fa-hammer',
                'title': f"Mutfak Montajı ({order.order_number})",
                'desc': "Ana mobilya modüllerinin kurulumu yapıldı.",
                'color': 'success'
            })
        if order.countertop_installation_date:
            events.append({
                'date': order.countertop_installation_date,
                'icon': 'fa-layer-group',
                'title': f"Tezgah Montajı ({order.order_number})",
                'desc': "Tezgah ölçümü ve montajı yapıldı.",
                'color': 'success'
            })
        if order.appliance_installation_date:
            events.append({
                'date': order.appliance_installation_date,
                'icon': 'fa-plug',
                'title': f"Cihaz Montajı ({order.order_number})",
                'desc': "Ankastre cihazlar ve beyaz eşyalar kuruldu.",
                'color': 'success'
            })
        if order.handover_date:
            events.append({
                'date': order.handover_date,
                'icon': 'fa-key',
                'title': f"Teslimat ve Devir ({order.order_number})",
                'desc': "Proje başarıyla müşteriye teslim edildi.",
                'color': 'success'
            })
            
        # 5. File Uploads
        for att in order.attachments:
            events.append({
                'date': att.upload_date,
                'icon': 'fa-image' if att.file_type == 'image' else 'fa-file-pdf',
                'title': f"Dosya Yüklendi: {att.context}",
                'desc': att.semantic_filename,
                'color': 'dark'
            })
            
        # 6. Customer Issues & Support
        for issue in order.issues:
            events.append({
                'date': issue.reported_date,
                'icon': 'fa-exclamation-triangle',
                'title': f"Müşteri Şikayeti / Talep: {issue.title}",
                'desc': issue.description,
                'color': 'danger'
            })
            if issue.investigation_date:
                events.append({
                    'date': issue.investigation_date,
                    'icon': 'fa-search',
                    'title': f"Çözüm İncelemesi: {issue.title}",
                    'desc': "Teknik ekip/satış temsilcisi konuyu inceliyor.",
                    'color': 'warning'
                })
            if issue.solution_date:
                events.append({
                    'date': issue.solution_date,
                    'icon': 'fa-check-double',
                    'title': f"Çözüm Teslimi: {issue.title}",
                    'desc': issue.resolution_notes or "Müşteri sorunu çözüldü.",
                    'color': 'success'
                })
                
    # Sort events newest to oldest
    events.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('arkhon/customer_detail.html', party=party, events=events)

@arkhon_bp.route('/order/<int:order_id>/update_milestones', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def update_milestones(order_id):
    """Updates the installation and handover milestones for an order."""
    order = db.get_or_404(Order, order_id)
    
    def parse_dt(date_str):
        if not date_str: return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            return None
            
    old_factory = order.factory_delivery_date
    old_appointment = order.installation_appointment_date
    old_kitchen = order.kitchen_installation_date
            
    order.factory_delivery_date = parse_dt(request.form.get('factory_delivery_date'))
    order.installation_appointment_date = parse_dt(request.form.get('installation_appointment_date'))
    order.kitchen_installation_date = parse_dt(request.form.get('kitchen_installation_date'))
    order.countertop_installation_date = parse_dt(request.form.get('countertop_installation_date'))
    order.appliance_installation_date = parse_dt(request.form.get('appliance_installation_date'))
    order.handover_date = parse_dt(request.form.get('handover_date'))
    
    db.session.commit()
    
    # --- AUTOMATED EMAIL NOTIFICATION SYSTEM ---
    notifications_sent = 0
    if order.party and order.party.email and '@crminaec.local' not in order.party.email:
        try:
            from flask_mail import Message

            from crminaec import mail
            
            messages_to_send = []
            
            factory_date = order.factory_delivery_date
            if factory_date and factory_date != old_factory:
                date_str = factory_date.strftime('%d.%m.%Y')
                messages_to_send.append(f"Ürünlerinizin fabrikadan depomuza tahmini varış tarihi {date_str} olarak güncellenmiştir.")
                
            appt_date = order.installation_appointment_date
            if appt_date and appt_date != old_appointment:
                date_str = appt_date.strftime('%d.%m.%Y %H:%M')
                messages_to_send.append(f"Montaj keşif/randevu tarihiniz {date_str} olarak belirlenmiştir.")
                
            kitchen_date = order.kitchen_installation_date
            if kitchen_date and kitchen_date != old_kitchen:
                date_str = kitchen_date.strftime('%d.%m.%Y %H:%M')
                messages_to_send.append(f"Mutfak montaj tarihiniz {date_str} olarak planlanmıştır.")
                
            if messages_to_send:
                body = f"Merhaba {order.party.first_name or ''},\n\nProjenizle ({order.order_number}) ilgili takvim güncellemeleri aşağıdadır:\n\n"
                for msg in messages_to_send:
                    body += f"- {msg}\n"
                body += "\nSürecin detaylarını Arkhon portalı üzerinden takip edebilirsiniz.\n\nSaygılarımızla,\nArkhon Mimarlık"
                
                email_msg = Message(
                    subject=f"Arkhon Mimarlık - Proje Takvimi Güncellemesi ({order.order_number})",
                    recipients=[order.party.email],
                    body=body
                )
                sender = current_app.config.get('MAIL_DEFAULT_SENDER')
                if sender: email_msg.sender = sender
                mail.send(email_msg)
                notifications_sent += 1
        except Exception as e:
            logger.error(f"Milestone notification failed: {e}")
            flash(f"Tarihler güncellendi ancak e-posta bildirimi gönderilemedi (E-posta sunucusu hatası).", "warning")
            return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

    if notifications_sent > 0:
        flash("Montaj tarihleri güncellendi ve müşteriye e-posta ile bildirildi.", "success")
    else:
        flash("Montaj ve teslimat tarihleri güncellendi.", "success")
        
    return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

# ==============================================================================
# 🏢 ARKHON DASHBOARD
# ==============================================================================

@arkhon_bp.route('/')
@login_required
def index():
    """Arkhon Dashboard / Order Overview"""
    try:
        show_archived = request.args.get('show_archived', '0') == '1'
        query = db.select(Order)
        
        # Hide soft-deleted orders from the main dashboard
        query = query.filter(Order.is_deleted.is_not(True))
        if not show_archived:
            query = query.filter(Order.is_archived.is_not(True))
        
        # DATA SEGREGATION: Customers only see their own orders
        if current_user.account.role not in ['admin', 'power_user']:
            query = query.filter(Order.party_id == current_user.party_id)
            
        recent_orders = db.session.scalars(query.order_by(Order.order_id.desc()).limit(10)).all()
        total_orders = db.session.scalar(db.select(db.func.count()).select_from(query.subquery())) or 0
        
        if current_user.account.role not in ['admin', 'power_user']:
            total_items = db.session.scalar(db.select(db.func.count(OrderItem.item_id)).join(Order).filter(Order.party_id == current_user.party_id)) or 0
        else:
            total_items = db.session.scalar(db.select(db.func.count(OrderItem.item_id))) or 0
        
        stats = {
            'total_orders': total_orders,
            'total_items': total_items
        }
        
        parties = []
        if current_user.account.role in ['admin', 'power_user']:
            parties = db.session.scalars(db.select(Party).order_by(Party.first_name)).all()
        
        return render_template('arkhon/arkhon_dashboard.html', orders=recent_orders, stats=stats, parties=parties)
    except Exception as e:
        logger.error(f"Dashboard load error: {e}")
        flash("Could not load dashboard data.", "error")
        return render_template('arkhon/arkhon_dashboard.html', orders=[], stats={}, parties=[])

@arkhon_bp.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    """View details of a specific parsed order"""
    order = db.get_or_404(Order, order_id)
    
    # OWNERSHIP GATE: Prevent customers from viewing others' orders
    if current_user.account.role not in ['admin', 'power_user'] and order.party_id != current_user.party_id:
        abort(403)
        
    # Fetch catalog items to populate the Add Appliance dropdown in the UI
    catalog_items = db.session.scalars(db.select(CatalogProduct)).all()
    
    # Fetch parties to populate the "Assign Customer" dropdown
    parties = []
    if current_user.account.role in ['admin', 'power_user']:
        parties = db.session.scalars(db.select(Party).order_by(Party.first_name)).all()
        
    return render_template('arkhon/order_detail.html', order=order, items=order.items, catalog_items=catalog_items, parties=parties)


@arkhon_bp.route('/order/<int:order_id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def delete_order(order_id):
    """Soft-delete an order so it can be restored later."""
    try:
        order = db.session.scalar(db.select(Order).filter_by(order_id=order_id))
        if order:
            order.is_deleted = True
            db.session.commit()
            flash(f"Sipariş #{order_id} silinenler kutusuna taşındı.", "success")
        else:
            flash("Order not found.", "error")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting order: {e}")
        flash("An error occurred while deleting the order.", "error")
        
    return redirect(url_for('arkhon.index'))

@arkhon_bp.route('/order/<int:order_id>/restore', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def restore_order(order_id):
    """Restores a soft-deleted order."""
    try:
        order = db.session.scalar(db.select(Order).filter_by(order_id=order_id))
        if order:
            order.is_deleted = False
            db.session.commit()
            flash(f"Sipariş #{order_id} başarıyla geri yüklendi.", "success")
        else:
            flash("Order not found.", "error")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error restoring order: {e}")
        flash("Sipariş geri yüklenirken bir hata oluştu.", "error")
        
    return redirect(url_for('arkhon.order_detail', order_id=order_id))

@arkhon_bp.route('/order/<int:order_id>/hard_delete', methods=['POST'])
@login_required
@role_required('admin')
def hard_delete_order(order_id):
    """Permanently deletes an order from the database (Admin Only)."""
    try:
        order = db.session.scalar(db.select(Order).filter_by(order_id=order_id))
        if order:
            db.session.delete(order)
            db.session.commit()
            flash(f"Sipariş #{order_id} kalıcı olarak tamamen silindi.", "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error hard deleting order: {e}")
        flash("Siparişi kalıcı silerken bir hata oluştu.", "danger")
    return redirect(url_for('arkhon.index'))

@arkhon_bp.route('/order/<int:order_id>/archive', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def archive_order(order_id):
    """Archives an order, hiding it from active views."""
    order = db.get_or_404(Order, order_id)
    order.is_archived = True
    db.session.commit()
    return redirect(url_for('arkhon.order_detail', order_id=order_id))

@arkhon_bp.route('/order/<int:order_id>/unarchive', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def unarchive_order(order_id):
    """Removes an order from the archive."""
    order = db.get_or_404(Order, order_id)
    order.is_archived = False
    db.session.commit()
    return redirect(url_for('arkhon.order_detail', order_id=order_id))

# ==============================================================================
# 📥 KELEBEK HTML IMPORT ROUTE
# ==============================================================================

@arkhon_bp.route('/order/import', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'power_user')
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
        new_order = Order(**{'order_number': generated_order_number})
        
        for item_data in parsed_items:
            safe_data = {k: v for k, v in item_data.items() if hasattr(OrderItem, k)}
            order_item = OrderItem(**safe_data)
            new_order.items.append(order_item)
            
        # --- AUTO-LINK CUSTOMER PARTY ---
        email = cust_info.get('email', '')
        first_name = cust_info.get('first_name', '')
        last_name = cust_info.get('last_name', '')
        
        if email or first_name or last_name:
            party = db.session.scalar(db.select(Party).filter_by(email=email)) if email else None
            if not party:
                party = Party(**{
                    'email': email if email else f"temp_{timestamp}@crminaec.local",
                    'first_name': first_name,
                    'last_name': last_name
                })
                db.session.add(party)
                db.session.flush()
            
            # Attach phone and address if model supports it
            if hasattr(party, 'phone') and cust_info.get('phone'):
                party.phone = cust_info.get('phone')
            if hasattr(party, 'address') and cust_info.get('address'):
                party.address = cust_info.get('address')
                
            new_order.party_id = party.party_id
            new_order.party = party

        db.session.add(new_order)
        db.session.commit()
        
        flash(f'Successfully imported order #{new_order.order_number} with {len(parsed_items)} items!', 'success')
        return redirect(url_for('arkhon.order_detail', order_id=new_order.order_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Order Import Failed: {e}")
        flash(f'A system error occurred during import: {str(e)}', 'error')
        return redirect(request.url)

@arkhon_bp.route('/order/<int:order_id>/import_kelebek', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def import_kelebek_for_order(order_id):
    """Appends items from a Kelebek HTML export to an existing order."""
    order = db.get_or_404(Order, order_id)
    
    if 'file' not in request.files:
        flash('No file part in the request.', 'danger')
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
        
    file = request.files['file']
    
    if not file.filename:
        flash('No file selected.', 'danger')
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
        
    if not file.filename.endswith('.html'):
        flash('Lütfen geçerli bir Kelebek HTML çıktısı yükleyin (.html).', 'danger')
        return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
        
    try:
        html_content = file.read().decode('utf-8', errors='ignore')
        parsed_data = KelebekOrderParser.parse_html(html_content)
        parsed_items = parsed_data.get('items', [])

        if not parsed_items:
            flash('Yüklenen HTML dosyasında geçerli ürün bulunamadı.', 'warning')
            return redirect(url_for('arkhon.order_detail', order_id=order.order_id))
            
        for item_data in parsed_items:
            safe_data = {k: v for k, v in item_data.items() if hasattr(OrderItem, k)}
            order.items.append(OrderItem(**safe_data))

        db.session.commit()
        flash(f'Başarıyla {len(parsed_items)} adet ürün {order.order_number} siparişine eklendi!', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Order Import Failed: {e}")
        flash(f'İçe aktarma sırasında bir sistem hatası oluştu: {str(e)}', 'danger')
        
    return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

@arkhon_bp.route('/order/<int:order_id>/assign_customer', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def assign_customer(order_id):
    """Assigns or updates the customer (Party) for an existing order."""
    order = db.get_or_404(Order, order_id)
    
    party_id = request.form.get('party_id')
    
    if party_id:
        party = db.session.get(Party, party_id)
        if party:
            order.party = party
            db.session.commit()
            flash("Müşteri siparişe başarıyla atandı.", "success")
        else:
            flash("Seçilen müşteri bulunamadı.", "danger")
    else:
        flash("Lütfen bir müşteri seçin.", "warning")
        
    return redirect(url_for('arkhon.order_detail', order_id=order.order_id))

# ==============================================================================
# 📥 PROSAP CSV IMPORT ROUTE
# ==============================================================================
@arkhon_bp.route('/order/<int:order_id>/import_prosap_csv', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
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
    if not prefs.plinth_height or not prefs.plinth_material: missing_fields.append("Baza Detayları")
    if not prefs.handle_code: missing_fields.append("Kulp Kodu/Modeli")
    
    if not prefs.appliance_refrigerator: missing_fields.append("Buzdolabı Checklist")
    if not prefs.appliance_dishwasher: missing_fields.append("Bulaşık Makinesi Checklist")
    if not prefs.appliance_washing_machine: missing_fields.append("Çamaşır Makinesi Checklist")
    if not prefs.appliance_oven_mw: missing_fields.append("Fırın/Mikrodalga Checklist")
    
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
@login_required
@role_required('admin', 'power_user')
def add_catalog_item(order_id):
    """Adds a standard catalog product (Appliance/Countertop) to an order."""
    order = db.get_or_404(Order, order_id)
    product_id = request.form.get('catalog_product_id')
    qty = float(request.form.get('qty', 1.0))
    
    if product_id:
        product = db.session.get(CatalogProduct, product_id)
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
@login_required
@role_required('admin', 'power_user')
def build_quote(order_id):
    """Internal UI to set ProSAP pricing, hide margin items, and generate a Quote."""
    order = db.get_or_404(Order, order_id)
    
    # Check if we are editing or duplicating an existing quote
    source_quote_id = request.args.get('source', type=int)
    edit_quote_id = request.args.get('edit', type=int)
    
    quote_to_load = None
    is_edit_mode = False
    
    if edit_quote_id:
        quote_to_load = db.session.scalar(db.select(Quote).filter_by(quote_id=edit_quote_id, order_id=order.order_id))
        is_edit_mode = True
    elif source_quote_id:
        quote_to_load = db.session.scalar(db.select(Quote).filter_by(quote_id=source_quote_id, order_id=order.order_id))

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
                current_quotes = db.session.scalar(db.select(db.func.count(Quote.quote_id)).filter_by(order_id=order.order_id)) or 0
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
@login_required
@role_required('admin', 'power_user')
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
@login_required
@role_required('admin', 'power_user')
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
@login_required
@role_required('admin', 'power_user')
def ghost_summary(order_id):
    """Generates the lean, unbranded totals page for negotiation."""
    order = db.get_or_404(Order, order_id)
    return render_template('arkhon/ghost_summary.html', order=order, current_date=datetime.now().strftime('%Y-%m-%d'))


@arkhon_bp.route('/customer/<int:party_id>/issue/new', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def create_issue(party_id):
    """Creates a new After-Sales Support ticket (Issue) for a customer's order."""
    order_id = request.form.get('order_id', type=int)
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    
    if not order_id or not title:
        flash("Sipariş seçimi ve Başlık zorunludur.", "danger")
        return redirect(url_for('arkhon.customer_detail', party_id=party_id))
        
    order = db.session.get(Order, order_id)
    if order and order.party_id == party_id:
        new_issue = CustomerIssue(**{'title': title, 'description': description})
        order.issues.append(new_issue)
        
        # --- HANDLE OPTIONAL FILE ATTACHMENT ---
        if 'issue_file' in request.files and request.files['issue_file'].filename:
            file = request.files['issue_file']
            
            # Apply Strict Naming Convention
            p = order.party
            fn = (p.first_name if p and p.first_name else 'XX').upper().strip()
            ln = (p.last_name if p and p.last_name else 'XXX').upper().strip()
            
            n_first = fn[0] if len(fn) > 0 else 'X'
            n_last = fn[-1] if len(fn) > 1 else (fn[0] if len(fn) > 0 else 'X')
            s_first = ln[0] if len(ln) > 0 else 'X'
            s_last = ln[-1] if len(ln) > 1 else (ln[0] if len(ln) > 0 else 'X')
            s_mid = ln[len(ln)//2] if len(ln) > 2 else 'X'
            
            date_str = datetime.now().strftime("%y%m%d%H%M")
            ext = os.path.splitext(str(file.filename))[1].lower()
            safe_context = re.sub(r'[^\w\s-]', '', title[:15]).strip().replace(' ', '_')
            
            semantic_filename = f"{n_first}{n_last}{s_first}{s_mid}{s_last}{date_str}_Sikayet_{safe_context}{ext}"
            
            upload_folder = os.path.join('crminaec', 'static', 'uploads', 'orders')
            os.makedirs(upload_folder, exist_ok=True)
            
            file_path = os.path.join(upload_folder, semantic_filename)
            file.save(file_path)
            
            file_type = "image" if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'] else "document"
            db_path = f"/static/uploads/orders/{semantic_filename}"
            
            new_attachment = OrderAttachment(**{
                'original_filename': str(file.filename),
                'semantic_filename': semantic_filename,
                'file_path': db_path,
                'file_type': file_type,
                'context': f'Şikayet / Talep Eki'
            }) # type: ignore
            order.attachments.append(new_attachment)
            
        db.session.commit()
        flash("Yeni destek talebi başarıyla oluşturuldu.", "success")
        
    return redirect(url_for('arkhon.customer_detail', party_id=party_id))

@arkhon_bp.route('/issue/<int:issue_id>/update', methods=['POST'])
@login_required
@role_required('admin', 'power_user')
def update_issue(issue_id):
    """Updates the status and resolution notes of a Support Ticket."""
    issue = db.get_or_404(CustomerIssue, issue_id)
    
    status = request.form.get('status')
    status = request.form.get('status') or 'Açık'
    issue.resolution_notes = request.form.get('resolution_notes', '').strip()
    issue.status = status
    
    if status == 'İncelemede' and not issue.investigation_date:
        issue.investigation_date = datetime.now()
    elif status == 'Çözüldü' and not issue.solution_date:
        issue.solution_date = datetime.now()
        
    db.session.commit()
    flash('Destek talebi güncellendi.', 'success')
    return redirect(url_for('arkhon.customer_detail', party_id=issue.order.party_id))

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
        quote.approval_date = datetime.now(timezone.utc)
        quote.approval_ip = request.remote_addr or 'Unknown IP' 
        
        db.session.commit()
        flash('Quote successfully approved! Your contract is being prepared.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while saving your approval.', 'danger')
        
    return redirect(url_for('arkhon.public_quote', access_token=access_token))

@arkhon_bp.route('/order/<int:order_id>/preferences', methods=['GET', 'POST'])
@login_required
def order_preferences(order_id):
    """Turkish UI for Müşteri ve Sipariş Takip Formu with Auto-Extraction."""
    order = db.get_or_404(Order, order_id)
    
    # OWNERSHIP GATE: Prevent customers from viewing/editing others' preferences
    if current_user.account.role not in ['admin', 'power_user'] and order.party_id != current_user.party_id:
        abort(403)
        
    # 1. AUTO-EXTRACTION ENGINE (Runs if preferences don't exist, OR if user forces a rebuild)
    rebuild = request.args.get('rebuild', type=int) == 1
    
    if not order.preferences or rebuild:
        prefs = order.preferences if order.preferences else ProjectPreference()
        
        if rebuild:
            prefs.model_name = None
            prefs.body_color = None
            prefs.front_color = None
            prefs.handle_code = None
            prefs.cabinet_grouping_notes = None
            prefs.plinth_height = None
            prefs.plinth_material = None
            prefs.plinth_color = None
            prefs.cutlery_tray = None
            prefs.trash_bin = None
            prefs.mechanisms = None
            prefs.glazed_door_model = None
            prefs.glazed_door_frame_color = None
            prefs.glazing_type = None
            prefs.appliance_refrigerator = None
            prefs.appliance_dishwasher = None
            prefs.appliance_washing_machine = None
            prefs.appliance_oven_mw = None
            
            prefs.light_cab_spot = False
            prefs.light_cab_led = None
            prefs.light_counter_spot = False
            prefs.light_counter_led = False
            prefs.light_bt_led = False
            prefs.sensor_dimmer = False
            prefs.sensor_door = False
            prefs.light_control_wall = False
            prefs.light_control_switch = False
            
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
                if not prefs.plinth_height:
                    prefs.plinth_height = "12cm" if "05" in str(item.urk) else "15cm"
                
            # Extract Accessories & Mechanisms
            if "kaşıklık" in name_lower or "kasiklik" in name_lower or "kaşıklığı" in name_lower:
                if not prefs.cutlery_tray:
                    prefs.cutlery_tray = item.ura
            if "çöp" in name_lower or "cop" in name_lower:
                if not prefs.trash_bin:
                    prefs.trash_bin = item.ura
                
            if any(x in name_lower for x in ["kiler", "kör köşe", "mekanizma", "şişelik", "siselik", "fasulye", "le mans"]):
                mechanisms_list.append(item.ura)
                
            # Extract Lighting & Sensors & Controls
            if "spot" in name_lower:
                if "tezgah" in name_lower or "tezgah arası" in name_lower:
                    prefs.light_counter_spot = True
                else:
                    prefs.light_cab_spot = True
            if "led" in name_lower or "aydınlatma" in name_lower:
                if "bluetooth" in name_lower:
                    prefs.light_bt_led = True
                elif "tezgah" in name_lower or "tezgah arası" in name_lower:
                    prefs.light_counter_led = True
                else:
                    prefs.light_cab_led = "Çift Yan" if "çift" in name_lower else "Tek Yan"
            if "sensör" in name_lower or "sensor" in name_lower:
                if "kapak" in name_lower:
                    prefs.sensor_door = True
                else:
                    prefs.sensor_dimmer = True

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
                party = db.session.scalar(db.select(Party).filter_by(email=cust_email)) if cust_email else None
                
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
            order.preferences.handle_code = request.form.get('handle_code')
            order.preferences.cabinet_grouping_notes = request.form.get('cabinet_grouping_notes')
            
            order.preferences.plinth_height = request.form.get('plinth_height')
            order.preferences.plinth_material = request.form.get('plinth_material')
            order.preferences.plinth_color = request.form.get('plinth_color')
            
            order.preferences.glazed_door_model = request.form.get('glazed_door_model')
            order.preferences.glazed_door_frame_color = request.form.get('glazed_door_frame_color')
            order.preferences.glazing_type = request.form.get('glazing_type')
            
            # Lighting & Sensors
            order.preferences.light_cab_spot = request.form.get('light_cab_spot') == 'on'
            order.preferences.light_cab_led = request.form.get('light_cab_led') or None
            order.preferences.light_counter_spot = request.form.get('light_counter_spot') == 'on'
            order.preferences.light_counter_led = request.form.get('light_counter_led') == 'on'
            order.preferences.light_bt_led = request.form.get('light_bt_led') == 'on'
            order.preferences.sensor_dimmer = request.form.get('sensor_dimmer') == 'on'
            order.preferences.sensor_door = request.form.get('sensor_door') == 'on'
            order.preferences.light_control_wall = request.form.get('light_control_wall') == 'on'
            order.preferences.light_control_switch = request.form.get('light_control_switch') == 'on'
            
            order.preferences.cutlery_tray = request.form.get('cutlery_tray')
            order.preferences.trash_bin = request.form.get('trash_bin')
            order.preferences.mechanisms = request.form.get('mechanisms')
            
            order.preferences.appliance_refrigerator = request.form.get('appliance_refrigerator')
            order.preferences.appliance_dishwasher = request.form.get('appliance_dishwasher')
            order.preferences.appliance_washing_machine = request.form.get('appliance_washing_machine')
            order.preferences.appliance_oven_mw = request.form.get('appliance_oven_mw')

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
@login_required
@role_required('admin', 'power_user')
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
    