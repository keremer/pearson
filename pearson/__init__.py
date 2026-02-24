"""
Pearson Course Management System
A comprehensive system for managing courses, lessons, and learning outcomes.
"""
__version__ = '1.0.0'
__author__ = 'Dr. Kerem ERCOŞKUN'
__email__ = 'ercoskunkerem@gmail.com'

import os
from pathlib import Path
from typing import Optional, Dict, Any

from flask import Flask

# Package metadata
__all__ = [
    'create_app', 'get_database_url', 'get_database_path', 'get_data_dir',
    'PROJECT_ROOT', 'DATA_DIR', 'CONFIG_DIR', 'TESTS_DIR',
    '__version__', '__author__', '__email__'
]

# Export commonly used paths
PACKAGE_ROOT = Path(__file__).parent.absolute()
PROJECT_ROOT = PACKAGE_ROOT.parent.absolute()
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
TESTS_DIR = PROJECT_ROOT / "tests"


def get_data_dir() -> Path:
    """Get the data directory path at project root."""
    # PACKAGE_ROOT is .../pearson/pearson
    # PROJECT_ROOT is .../pearson
    package_root = Path(__file__).parent.absolute()
    project_root = package_root.parent.absolute()
    
    data_dir = project_root / "data"
    
    # Force creation of the directory with parents
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_database_path(db_name: str = 'courses.db') -> Path:
    """Get the full path to the database file."""
    return get_data_dir() / db_name


def get_database_url(db_name: str = 'courses.db') -> str:
    """Get the SQLAlchemy database URL with a clean absolute path."""
    db_path = get_database_path(db_name)
    # On Windows, we need to ensure the path is absolute and uses forward slashes
    return f'sqlite:///{db_path.as_posix()}'


def create_app(config: Optional[Dict[str, Any]] = None) -> Flask:
    """
    Create and configure the Flask application.
    
    Returns:
        Flask: Configured Flask application instance
    """
    # PACKAGE_ROOT is .../pearson/pearson
    package_root = Path(__file__).parent.absolute()
    # PROJECT_ROOT is .../pearson
    project_root = package_root.parent.absolute()

    # Create Flask app
    app = Flask(__name__, 
                instance_relative_config=True,
                static_folder=str(project_root / 'static'),
                static_url_path='/static')
    
    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
        DATABASE_URL=os.environ.get('DATABASE_URL', get_database_url()),
        DATA_DIR=str(get_data_dir()),
        WTF_CSRF_ENABLED=True,
        TESTING=False,
        DEBUG=os.environ.get('FLASK_DEBUG', '0').lower() in ['1', 'true', 'yes'],
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max upload
        UPLOAD_FOLDER=str(PROJECT_ROOT / 'static' / 'uploads'),
        ALLOWED_EXTENSIONS={'md'},
    )
    
    # Update with any provided config
    if config:
        app.config.update(config)
    
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    
    # Initialize database setup in app context
    _db_initialized = False
    
    @app.before_request
    def initialize_database():
        """Initialize database on first request."""
        nonlocal _db_initialized
        if not _db_initialized:
            from pearson.cli.setup import DatabaseSetup
            db_setup = DatabaseSetup(app.config['DATABASE_URL'])
            app.config['db_setup'] = db_setup
            print(f"📦 Database initialized: {app.config['DATABASE_URL']}")
            _db_initialized = True
    
    # Register Web Blueprints
    try:
        from pearson.web import web_bp
        app.register_blueprint(web_bp)
    except ImportError as e:
        print(f"⚠️  Could not register web blueprint: {e}")

    # --- NEW: Proper API Binding ---
    try:
        # Import and initialize the course-related API routes
        from pearson.api.courses import init_course_routes
        init_course_routes(app)
        print("🔗 API routes bound successfully")
    except ImportError as e:
        print(f"⚠️  Could not initialize API routes: {e}")
    # -------------------------------
    
    # Register CLI commands
    @app.cli.command("init-db")
    def init_db_command():
        """Initialize the database."""
        from pearson.cli.setup import DatabaseSetup
        db_setup = DatabaseSetup(app.config['DATABASE_URL'])
        db_setup.create_tables()
        print("Database initialized.")
    
    @app.cli.command("reset-db")
    def reset_db_command():
        """Reset the database."""
        from pearson.cli.setup import DatabaseSetup
        db_setup = DatabaseSetup(app.config['DATABASE_URL'])
        db_setup.drop_tables()
        db_setup.create_tables()
        print("Database reset.")
    
    print(f"📦 Pearson package initialized (root: {PROJECT_ROOT})")
    
    return app


# Backward compatibility function
def init_app(config: Optional[Dict[str, Any]] = None):
    """
    Backward compatibility wrapper for create_app.
    Returns tuple (app, db_setup) for compatibility with existing code.
    """
    print("⚠️  init_app is deprecated, use create_app instead")
    app = create_app(config)
    
    # Initialize db_setup immediately for backward compatibility
    from pearson.cli.setup import DatabaseSetup
    db_setup = DatabaseSetup(app.config['DATABASE_URL'])
    app.config['db_setup'] = db_setup
    
    return app, db_setup