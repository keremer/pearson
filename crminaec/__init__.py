# crminaec/__init__.py
import os
from pathlib import Path
from typing import cast

from authlib.integrations.flask_client import OAuth
from flask import Flask, render_template
from flask_login import LoginManager
from flask_mail import Mail
from werkzeug.middleware.proxy_fix import ProxyFix

# Use the dynamic config loader
from crminaec.config import Config, get_config
from crminaec.core.models import Party, db


class AutoSchemeMiddleware:
    """Dynamically routes HTTP/HTTPS based on the requested Host domain."""
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # IIS overwrites HTTP_HOST before ProxyFix runs, so we must check X-Forwarded-Host
        host = str(environ.get('HTTP_X_FORWARDED_HOST') or environ.get('HTTP_HOST') or '')
        # Force HTTPS if accessed via the production domain
        environ['wsgi.url_scheme'] = 'https' if 'crminaec.com' in host else 'http'
        return self.app(environ, start_response)

# Initialize extensions globally
login_manager = LoginManager()
oauth = OAuth()
mail=Mail()


class AppFactory:
    @staticmethod
    def create_app(config_name=None):
        project_root = Path(__file__).parent.parent.absolute()
        
        app = Flask(__name__, template_folder='web/templates')
        
        #1. LOAD DYNAMIC CONFIGURATION
        config_class = get_config(config_name)
        app.config.from_object(config_class)
        
        # 2. TRIGGER ENVIRONMENT-SPECIFIC SETUP
        config_class.init_app(app)

        # 🚨 CUSTOM MIDDLEWARE
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=0, x_host=1, x_prefix=1) # type: ignore
        
        # Automatically switch to HTTPS for live domains to bypass IIS limitations
        app.wsgi_app = AutoSchemeMiddleware(app.wsgi_app)

        AppFactory._prepare_environment(app, project_root)

        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            db_path = project_root / 'data' / 'portal.db'
            app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"

        db.init_app(app)
        mail.init_app(app)

        # ==========================================
        # 🔐 FLASK-LOGIN SETUP
        # ==========================================
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login' # type: ignore
        login_manager.login_message = "Lütfen giriş yapınız."

        @login_manager.user_loader
        def load_user(party_id):
            return db.session.get(Party, int(party_id))

        # ==========================================
        # 🔑 GOOGLE OAUTH SETUP (The Missing Piece)
        # ==========================================
        oauth.init_app(app)
        oauth.register(
            name='google',
            client_id=app.config.get('GOOGLE_CLIENT_ID'),
            client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )

        # ==============================================================
        # 🔗 IMPORT AND REGISTER BLUEPRINTS
        # ==============================================================

        from crminaec.auth.routes import auth_bp
        from crminaec.platforms.arkhon.routes import arkhon_bp
        from crminaec.platforms.emek.routes import emek_bp
        from crminaec.platforms.pearson.routes import pearson_bp
        from crminaec.routes import main_bp
        
        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(pearson_bp, url_prefix='/pearson')
        app.register_blueprint(arkhon_bp, url_prefix='/arkhon')
        app.register_blueprint(emek_bp, url_prefix='/emek')
        
        # 3. Initialize API & Webhook Routes
        from crminaec.api.courses import init_course_routes
        from crminaec.api.webhooks import init_webhook_routes
        
        init_course_routes(app)
        init_webhook_routes(app)

        return app

    @staticmethod
    def _prepare_environment(app, project_root):
        import os
        folders = [
            os.path.join(project_root, app.config.get('UPLOAD_FOLDER', 'static/uploads')), 
            os.path.join(project_root, 'data')
        ]
        for f in folders:
            os.makedirs(f, exist_ok=True)

def create_app(config_name=None):
    return AppFactory.create_app(config_name)

def get_database_url() -> str:
    # Get the active config based on the current environment
    active_config = get_config()
    url = active_config.SQLALCHEMY_DATABASE_URI or "sqlite:///data/portal.db"
    return cast(str, url)