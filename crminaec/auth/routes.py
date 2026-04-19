# crminaec/auth/routes.py
import datetime

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
from flask_login import login_required, login_user, logout_user
from werkzeug.exceptions import NotFound

from crminaec import oauth
from crminaec.core.models import Party, UserAccount, db
from crminaec.core.security import confirm_token, generate_confirmation_token

auth_bp = Blueprint('auth', __name__)

# --- 1. Traditional Login (Modernized) ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Grab email instead of username
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Query the CRM Party
        party = db.session.query(Party).filter_by(email=email).first()
        
        # Check if they exist AND if they have a linked portal account with a valid password
        if party and party.account and password and party.account.check_password(password):
            # Assuming your Party class implements Flask-Login's UserMixin
            login_user(party)
            return redirect(url_for('main.index'))
            
        flash('Geçersiz e-posta veya şifre.', 'danger')
    return render_template('auth/login.html')

# --- 2. Google Login Initiation ---
@auth_bp.route('/login/google')
def google_login():
    # Double safety: Force HTTPS scheme if the request originated from the live domain
    x_host = request.headers.get('X-Forwarded-Host') or ''
    live_domain = 'crminaec.com' in request.host or 'crminaec.com' in x_host
    if live_domain:
        redirect_uri = url_for('auth.google_callback', _external=True, _scheme='https')
    else:
        redirect_uri = url_for('auth.google_callback', _external=True)
    # 🚨 Force redirect_uri as a keyword argument so Authlib doesn't drop it
    return oauth.google.authorize_redirect(redirect_uri=redirect_uri, prompt='select_account') # type: ignore

# --- 3. Google Callback Handler (Modernized) ---
@auth_bp.route('/login/google/callback')
def google_callback():
    token = oauth.google.authorize_access_token() # type: ignore
    user_info = token.get('userinfo')
    
    if not user_info:
        flash("Google girişi başarısız.", 'danger')
        return redirect(url_for('auth.login'))

    email = user_info.get('email')
    party = db.session.query(Party).filter_by(email=email).first()

    # If the email isn't in our database yet, create BOTH records
    if not party:
        # 1. Create Party (NO username parameter here!)
        party = Party(**{
            'email': email,
            'first_name': user_info.get('given_name'),
            'last_name': user_info.get('family_name')
        })
        db.session.add(party)
        db.session.flush() # Get the party_id
        
        # 2. Create the UserAccount (This is where the role goes!)
        # Google users bypass the password requirement because Google authenticated them
        # We assign a random impossibly-long password hash just to satisfy the database
        import secrets
        new_account = UserAccount(**{
            'party_id': party.party_id,
            'role': "guest",
            'is_confirmed': True,
            'confirmed_on': datetime.datetime.utcnow(),
            'kvkk_approved': True,
            'kvkk_approval_date': datetime.datetime.utcnow(),
            'kvkk_approval_ip': request.remote_addr or '0.0.0.0'
        })
        new_account.set_password(secrets.token_urlsafe(32))
        party.account = new_account
        db.session.add(new_account)
        db.session.commit()
    
    # If they existed as a CRM contact but had no account, attach one
    elif not party.account:
        import secrets
        new_account = UserAccount(**{
            'party_id': party.party_id,
            'role': "guest",
            'is_confirmed': True,
            'confirmed_on': datetime.datetime.utcnow(),
            'kvkk_approved': True,
            'kvkk_approval_date': datetime.datetime.utcnow(),
            'kvkk_approval_ip': request.remote_addr or '0.0.0.0'
        })
        new_account.set_password(secrets.token_urlsafe(32))
        party.account = new_account
        db.session.add(new_account)
        db.session.commit()

    login_user(party)
    return redirect(url_for('main.index'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # 1. Extract Form Data (Ensure your HTML form has first_name and last_name inputs!)
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        kvkk_consent = request.form.get('kvkk_consent') == 'on'
        
        if not password:
            flash('Şifre alanı boş olamaz.', 'danger')
            return redirect(url_for('auth.register'))
        
        if not kvkk_consent:
            flash('Kayıt olmak için KVKK Aydınlatma Metnini onaylamanız gerekmektedir.', 'danger')
            return redirect(url_for('auth.register'))
            
        # 2. Query the PARTY table (because that is where the email lives)
        existing_party = db.session.query(Party).filter_by(email=email).first()
        
        if existing_party:
            # Check if this CRM contact already claimed a portal account
            if existing_party.account:
                flash('Bu e-posta adresi sistemde zaten kayıtlı.', 'warning')
                return redirect(url_for('auth.register'))
            else:
                # ACCOUNT CLAIMING: Use the existing CRM record
                party = existing_party
                if not party.first_name and first_name: party.first_name = first_name
                if not party.last_name and last_name: party.last_name = last_name
        else:
            # NEW USER: Create the Party record first
            party = Party(**{
                'email': email,
                'first_name': first_name,
                'last_name': last_name
            })
            db.session.add(party)
            # flush() asks the DB for the new party_id without finalizing the commit yet
            db.session.flush() 
            
        # 3. Create the UserAccount using the party_id
        new_user = UserAccount(**{
            'party_id': party.party_id,
            'kvkk_approved': True,
            'kvkk_approval_date': datetime.datetime.utcnow(),
            'kvkk_approval_ip': request.remote_addr or '0.0.0.0',
            'role': 'customer'
        })
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        # 4. Generate token and send email
        from crminaec.core.email import send_confirmation_email
        token = generate_confirmation_token(party.email)
        confirm_url = url_for('auth.confirm_email', token=token, _external=True)
        
        email_sent = send_confirmation_email(party.email, confirm_url)
        
        if email_sent:
            flash('Kayıt başarılı! Lütfen e-posta adresinize gönderilen onay linkine tıklayın. (Link 1 saat geçerlidir)', 'success')
        else:
            flash('Kayıt başarılı, ancak onay e-postası gönderilirken bir hata oluştu.', 'warning')
            
        return redirect(url_for('auth.login'))
        
    return render_template('arkhon/register.html')

@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
    except:
        flash('Onay linki geçersiz veya süresi dolmuş (1 saatlik süre aşılmış olabilir).', 'danger')
        return redirect(url_for('auth.login'))
        
    # Query the Party first, then access the linked account
    party = db.session.query(Party).filter_by(email=email).first()
    if not party:
        raise NotFound("Party not found")
    user_account = party.account
    
    if not user_account:
        flash('Sistemde bu e-postaya ait portal yetkisi bulunamadı.', 'danger')
        return redirect(url_for('auth.register'))
    
    if user_account.is_confirmed:
        flash('Hesabınız zaten onaylanmış. Lütfen giriş yapın.', 'info')
    else:
        user_account.is_confirmed = True
        user_account.confirmed_on = datetime.datetime.utcnow()
        db.session.commit()
        flash('E-posta adresiniz başarıyla onaylandı. Sisteme giriş yapabilirsiniz.', 'success')
        
    return redirect(url_for('auth.login'))