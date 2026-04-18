# crminaec/routes.py
import datetime
import secrets

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required, login_user, logout_user

from crminaec import oauth
from crminaec.core.models import Party, UserAccount, db  # 🚨 Added UserAccount

main_bp = Blueprint('main', __name__)

# ==========================================
# 🚦 THE TRAFFIC COP (Root Index)
# ==========================================
@main_bp.route('/')
@login_required
def index():
    # 1. Safety check: Ensure they actually have a portal account linked
    if not current_user.account:
        return "Sisteme giriş yetkiniz bulunmamaktadır.", 403

    # 2. Check the role on the linked UserAccount!
    user_role = current_user.account.role

    if user_role == "admin":
        return redirect(url_for('emek.bom_editor')) 
    elif user_role == "architect":
        return redirect(url_for('arkhon.dashboard'))
    elif user_role == "instructor":
        return redirect(url_for('pearson.courses'))
    else:
        return render_template('portal_home.html')

# ==========================================
# 🔐 AUTHENTICATION ROUTES
# ==========================================
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email') # 🚨 Changed to email
        password = request.form.get('password')
        
        party = db.session.query(Party).filter_by(email=email).first()
        
        # 🚨 Verify the linked account and check the hashed password
        if party and party.account and password and party.account.check_password(password): 
            login_user(party)
            return redirect(url_for('main.index'))
        
        flash('Geçersiz e-posta veya şifre.', 'danger')
    return render_template('auth/login.html')

@main_bp.route('/login/google')
def google_login():
    """Redirects the user to Google's OAuth consent screen."""
    exact_redirect_uri = current_app.config.get('GOOGLE_CALLBACK_URL')
    return oauth.google.authorize_redirect(exact_redirect_uri)

@main_bp.route('/login/google/callback')
def google_callback():
    """Handles the response from Google and logs the Party in."""
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info:
        flash("Google girişi başarısız.", "danger")
        return redirect(url_for('main.login'))

    email = user_info.get('email')
    party = db.session.query(Party).filter_by(email=email).first()

    # 🚨 Dual-Table Creation Logic for Google Users
    if not party:
        # 1. Create CRM Party
        party = Party(
            email=email, #type: ignore
            first_name=user_info.get('given_name'), #type: ignore
            last_name=user_info.get('family_name') #type: ignore
        )
        db.session.add(party)
        db.session.flush() # Get party_id without full commit
        
        # 2. Create Security Account
        new_account = UserAccount(
            party_id=party.party_id, #type: ignore
            role="guest",           #type: ignore
            is_confirmed=True,       #type: ignore
            confirmed_on=datetime.datetime.utcnow(), #type: ignore               
            kvkk_approved=True,     #type: ignore
            kvkk_approval_date=datetime.datetime.utcnow(),  #type: ignore
            kvkk_approval_ip=request.remote_addr or '0.0.0.0'   #type: ignore
        )
        new_account.set_password(secrets.token_urlsafe(32))
        db.session.add(new_account)
        db.session.commit()
        
    elif not party.account:
        # If they existed as a CRM contact but had no account
        new_account = UserAccount(
            party_id=party.party_id,    #type: ignore
            role="guest",               #type: ignore   
            is_confirmed=True,          #type: ignore
            kvkk_approved=False,         #type: ignore   
            confirmed_on=datetime.datetime.utcnow() , #type: ignore
        )
        new_account.set_password(secrets.token_urlsafe(32))
        db.session.add(new_account)
        db.session.commit()

    login_user(party)
    return redirect(url_for('main.index'))

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))