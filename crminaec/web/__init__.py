"""
Web interface blueprint for crminaec Course Management System.
"""
from flask import Blueprint

pearson_bp = Blueprint('web', __name__, 
                   template_folder='templates',
                   static_folder='static',
                   url_prefix='')

# def create_app(config=None):
#     """
#     Application factory for creating Flask app.
    
#     Args:
#         config (dict): Configuration dictionary
        
#     Returns:
#         Flask: Configured Flask application
#     """
#     from flask import Flask
    
#     app = Flask(__name__)
    
#     # Default configuration
#     default_config = {
#         'SECRET_KEY': 'dev-secret-key-change-in-production',
#         'WTF_CSRF_ENABLED': True,
#         'TESTING': False,
#     }
    
#     app.config.update(default_config)
#     if config:
#         app.config.update(config)
    
#     # Register blueprint
#     app.register_blueprint(pearson_bp)
    
#     return app

# Import routes after creating blueprint to avoid circular imports
from crminaec.web import routes