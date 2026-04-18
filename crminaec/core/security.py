# crminaec/core/security.py
from functools import wraps

from flask import abort, current_app, redirect, url_for
from flask_login import current_user
from itsdangerous import URLSafeTimedSerializer


def role_required(*roles):
    """
    Blocks access to a route unless the user's Party.role matches one of the allowed roles.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Are they logged in at all?
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # 2. Does their Party role match the required roles?
            if not current_user.account or current_user.account.role not in roles:
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# crminaec/core/security.py



def generate_confirmation_token(email):
    """Generates a secure, URL-safe token encoding the user's email."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    # You should add SECURITY_PASSWORD_SALT to your .env and config.py
    return serializer.dumps(email, salt=current_app.config.get('SECURITY_PASSWORD_SALT', 'default-salt-value'))

def confirm_token(token, expiration=3600):
    """Decodes the token. Expires after 1 hour (3600 seconds) by default."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config.get('SECURITY_PASSWORD_SALT', 'default-salt-value'),
            max_age=expiration
        )
    except Exception:
        return False
    return email