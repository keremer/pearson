# crminaec/routes.py
import datetime
import secrets

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, send_from_directory, session, url_for)
from flask_login import current_user, login_required, login_user, logout_user

from crminaec.core.models import Party, UserAccount, db
from crminaec.core.security import role_required

main_bp = Blueprint('main', __name__)

# ==========================================
# 🚦 THE TRAFFIC COP (Root Index)
# ==========================================
@main_bp.route('/')
@login_required
def index():
    # 1. Safety check: Ensure they actually have a portal account linked
    if not current_user.account: # type: ignore
        logout_user()
        flash("Sisteme giriş yetkiniz bulunmamaktadır veya hesabınız güncel değil. Lütfen tekrar giriş yapın.", "warning")
        return redirect(url_for('auth.login'))

    # 2. Check the role on the linked UserAccount!
    user_role = current_user.account.role # type: ignore

    if user_role == "power_user":
        return redirect(url_for('arkhon.dashboard'))
    elif user_role == "instructor":
        return redirect(url_for('pearson.courses'))
    else:
        return render_template('portal_home.html')

# ==========================================
# 📱 PWA / SERVICE WORKER
# ==========================================
@main_bp.route('/service-worker.js')
def service_worker():
    """Serves the PWA Service Worker from the root scope to allow full app control."""
    return send_from_directory(current_app.static_folder, 'service-worker.js', mimetype='application/javascript')

# ==========================================
# 🔐 ADMIN: USER MANAGEMENT
# ==========================================
@main_bp.route('/admin/users', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def manage_users():
    if request.method == 'POST':
        party_id = request.form.get('party_id')
        new_role = request.form.get('role')
        is_confirmed = request.form.get('is_confirmed') == 'on'
        
        if not party_id or not new_role:
            flash('Gerekli alanlar eksik.', 'error')
            return redirect(url_for('main.manage_users'))
        
        party = db.session.get(Party, int(party_id))
        if party:
            if new_role == 'none':
                if party.account:
                    db.session.delete(party.account)
                    flash(f'{party.first_name or "Kullanıcı"} adlı kişinin portal erişimi kaldırıldı.', 'success')
            else:
                if not party.account:
                    new_account = UserAccount(**{
                        'party_id': party.party_id,
                        'party': party,
                        'role': new_role,
                        'is_confirmed': is_confirmed,
                        'kvkk_approved': True,
                        'kvkk_approval_date': datetime.datetime.utcnow(),
                        'kvkk_approval_ip': request.remote_addr or '127.0.0.1'
                    })
                    new_account.set_password(secrets.token_urlsafe(32))
                    db.session.add(new_account)
                    flash(f'{party.first_name or "Kullanıcı"} için {new_role} rolüyle portal hesabı oluşturuldu.', 'success')
                else:
                    party.account.role = new_role
                    party.account.is_confirmed = is_confirmed
                    flash(f'{party.first_name or "Kullanıcı"} yetkileri başarıyla güncellendi.', 'success')
            db.session.commit()
            
        return redirect(url_for('main.manage_users'))
        
    users = db.session.query(Party).all()
    return render_template('admin/manage_users.html', users=users)

@main_bp.route('/admin/users/edit_party', methods=['POST'])
@login_required
@role_required('admin')
def edit_party():
    """Allows admins to update a Party's personal details directly from the Admin Panel."""
    party_id = request.form.get('party_id')
    party = db.session.get(Party, int(party_id))
    
    if party:
        party.first_name = request.form.get('first_name', '').strip()
        party.last_name = request.form.get('last_name', '').strip()
        party.email = request.form.get('email', '').strip()
        
        if hasattr(party, 'phone'):
            party.phone = request.form.get('phone', '').strip()
        if hasattr(party, 'address'):
            party.address = request.form.get('address', '').strip()
            
        db.session.commit()
        flash(f"{party.first_name or 'Kullanıcı'} bilgileri başarıyla güncellendi.", "success")
        
    return redirect(url_for('main.manage_users'))

@main_bp.route('/admin/impersonate/<int:party_id>', methods=['POST'])
@login_required
@role_required('admin')
def impersonate(party_id):
    """Temporarily log in as a specific user to test their viewpoint."""
    target_party = db.session.get(Party, party_id)
    if not target_party or not target_party.account:
        flash('Kullanıcı veya portal hesabı bulunamadı.', 'danger')
        return redirect(url_for('main.manage_users'))
    
    admin_id = current_user.party_id
    login_user(target_party)
    
    session['impersonator_id'] = admin_id
    
    flash(f"{target_party.first_name or 'Müşteri'} görünümüne geçildi.", 'success')
    return redirect(url_for('main.index'))

@main_bp.route('/admin/stop_impersonate')
@login_required
def stop_impersonate():
    """Return to the admin account from an impersonated session."""
    if 'impersonator_id' in session:
        admin_id = session.pop('impersonator_id')
        admin_party = db.session.get(Party, admin_id)
        if admin_party:
            login_user(admin_party)
            flash('Admin görünümüne geri dönüldü.', 'success')
            return redirect(url_for('main.manage_users'))
    return redirect(url_for('main.index'))

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Allows the logged-in user to update their contact info and password."""
    if request.method == 'POST':
        # Update personal information
        current_user.first_name = request.form.get('first_name', '').strip()
        current_user.last_name = request.form.get('last_name', '').strip()
        current_user.phone = request.form.get('phone', '').strip()
        current_user.address = request.form.get('address', '').strip()
        
        # Update password if requested
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password:
            if new_password == confirm_password:
                current_user.account.set_password(new_password)
                flash('Şifreniz başarıyla güncellendi.', 'success')
            else:
                flash('Yeni şifreler eşleşmiyor.', 'danger')
                return redirect(url_for('main.profile'))
                
        db.session.commit()
        flash('Profil bilgileriniz başarıyla kaydedildi.', 'success')
        return redirect(url_for('main.profile'))
        
    return render_template('profile.html', user=current_user)