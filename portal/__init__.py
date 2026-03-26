"""
crminaec Course Management System
A comprehensive system for managing courses, lessons, and learning outcomes.
"""
__version__ = '1.0.0'
__author__ = 'Dr. Kerem ERCOŞKUN'
__email__ = 'ercoskunkerem@gmail.com'

import os
from typing import cast

from config import Config
from flask import Blueprint, Flask, render_template

# Define the blueprint here
# Note: name='pearson' is better than 'web' to avoid confusion with Arkhon
pearson_bp = Blueprint(
    'pearson', 
    __name__, 
    template_folder='templates',
    static_folder='static'
)

arkhon_bp = Blueprint(
    'arkhon', 
    __name__, 
    template_folder='templates',
    static_folder='static'
)

emek_bp = Blueprint(
    'emek', 
    __name__, 
    template_folder='templates',
    static_folder='static'
)
class AppFactory:
    """The dedicated class for creating and configuring the crminaec Portal"""
    
    @staticmethod
    def create_app(config_class=Config):
        app = Flask(__name__)
        app.config.from_object(config_class)

        # Ensure required folders exist (Academic Specs, Uploads, etc.)
        AppFactory._prepare_environment(app)

        # Register Blueprints (The Platforms)
        AppFactory._register_blueprints(app)

        # Global Portal Landing Page
        @app.route('/')
        def index():
            return render_template('portal_home.html')

        return app

    @staticmethod
    def _prepare_environment(app):
        """Logic to ensure local storage and content folders exist"""
        folders = [
            app.config.get('CONTENT_DIR', 'content'),
            app.config.get('UPLOAD_FOLDER', 'content/uploads'),
            'data'
        ]
        for folder in folders:
            os.makedirs(folder, exist_ok=True)

    @staticmethod
    def _register_blueprints(app):
        # """Wiring up Pearson and Arkhon platforms"""
        # from portal.platforms.pearson import pearson_bp
        # # from portal.platforms.arkhon import arkhon_bp
        
        app.register_blueprint(pearson_bp, url_prefix='/pearson')
        app.register_blueprint(arkhon_bp, url_prefix='/arkhon')
        app.register_blueprint(emek_bp, url_prefix='/emek')
# The standard entry point for Flask extensions and run.py
def create_app():
    return AppFactory.create_app()

def get_database_url() -> str:
    # Use 'or' to provide a fallback, ensuring the return is always a str
    url = Config.SQLALCHEMY_DATABASE_URI or "sqlite:///data/courses.db"
    return cast(str, url)