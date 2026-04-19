# crminaec/routes.py
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user

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

    if user_role == "architect":
        return redirect(url_for('arkhon.dashboard'))
    elif user_role == "instructor":
        return redirect(url_for('pearson.courses'))
    else:
        return render_template('portal_home.html')

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
        if party and party.account:
            party.account.role = new_role
            party.account.is_confirmed = is_confirmed
            db.session.commit()
            flash(f'{party.first_name} {party.last_name} kullanıcısının yetkileri güncellendi.', 'success')
        return redirect(url_for('main.manage_users'))
        
    users = db.session.query(Party).all()
    return render_template('admin/manage_users.html', users=users)