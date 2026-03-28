import os
from typing import cast

from flask import Blueprint, Flask, render_template

from crminaec.config import Config
# IMPORTANT: Using the correct 'crminaec' package name
from crminaec.core.models import db

# Define Blueprints for different business units
pearson_bp = Blueprint('pearson', __name__, template_folder='platforms/pearson/templates')
arkhon_bp = Blueprint('arkhon', __name__, template_folder='platforms/arkhon/templates')
emek_bp = Blueprint('emek', __name__, template_folder='platforms/emek/templates')

class AppFactory:
    @staticmethod
    def create_app(config_class=Config):
        import os
        from pathlib import Path

        # Determine the absolute project root (e.g., C:\...\Portal)
        project_root = Path(__file__).parent.parent.absolute()
        
        app = Flask(__name__)
        app.config.from_object(config_class)

        # 1. Ensure folders exist BEFORE database initialization
        AppFactory._prepare_environment(app, project_root)

        # 2. Absolute Pathing for SQLite fallback
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            # This creates an absolute path like sqlite:///C:/.../Portal/data/portal.db
            db_path = project_root / 'data' / 'portal.db'
            app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"

        # 3. Initialize the database extension
        db.init_app(app)

        # 4. Register Business Blueprints
        app.register_blueprint(pearson_bp, url_prefix='/pearson')
        app.register_blueprint(arkhon_bp, url_prefix='/arkhon')
        app.register_blueprint(emek_bp, url_prefix='/emek')

        # 5. Initialize API & Webhook Routes
        from crminaec.api.courses import init_course_routes
        from crminaec.api.webhooks import init_webhook_routes
        
        init_course_routes(app)
        init_webhook_routes(app)

        # Global Portal Landing Page
        @app.route('/')
        def index():
            return render_template('portal_home.html')

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

def create_app():
    return AppFactory.create_app()

def get_database_url() -> str:
    url = Config.SQLALCHEMY_DATABASE_URI or "sqlite:///data/portal.db"
    return cast(str, url)