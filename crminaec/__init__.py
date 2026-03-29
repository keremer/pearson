import os
from pathlib import Path
from typing import cast

from flask import Flask, render_template

from crminaec.config import Config
from crminaec.core.models import db


class AppFactory:
    @staticmethod
    def create_app(config_class=Config):
        # Determine the absolute project root (e.g., C:\...\Portal)
        project_root = Path(__file__).parent.parent.absolute()
        
        # Point to the new centralized templates folder!
        app = Flask(__name__, template_folder='web/templates')
        app.config.from_object(config_class)

        # Ensure folders exist
        AppFactory._prepare_environment(app, project_root)

        # Absolute Pathing for SQLite fallback
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            db_path = project_root / 'data' / 'portal.db'
            app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"

        # Initialize the database extension
        db.init_app(app)

        # ==============================================================
        # 🔗 IMPORT AND REGISTER BLUEPRINTS
        # Now they are imported fully loaded with their routes!
        # ==============================================================
        from crminaec.platforms.arkhon.routes import arkhon_bp
        from crminaec.platforms.pearson.routes import pearson_bp
        
        app.register_blueprint(pearson_bp, url_prefix='/pearson')
        app.register_blueprint(arkhon_bp, url_prefix='/arkhon')

        # Initialize API & Webhook Routes
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