"""
Pearson Course Management System
A comprehensive system for managing courses, lessons, and learning outcomes.
"""
__version__ = '1.0.0'
__author__ = 'Dr. Kerem ERCOŞKUN'
__email__ = 'ercoskunkerem@gmail.com'

import os
import sys
from pathlib import Path

# Add the project root to Python path for consistent imports
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Export commonly used paths
PROJECT_ROOT = project_root
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
TESTS_DIR = PROJECT_ROOT / "tests"

# Clean up
del project_root

# Package metadata
__all__ = [
    'Course', 'Lesson', 'LearningOutcome', 'AssessmentFormat', 
    'Tool', 'LessonLearningOutcome', 'DatabaseSetup', 'CourseInjector',
    'web_bp'
]

# Database configuration
def get_data_dir():
    """Get the data directory path."""
    data_dir = PROJECT_ROOT / 'data'
    data_dir.mkdir(exist_ok=True)
    return data_dir

def get_database_path(db_name='courses.db'):
    """Get the full path to the database file."""
    return get_data_dir() / db_name

def get_database_url(db_name='courses.db'):
    """Get the SQLAlchemy database URL."""
    db_path = get_database_path(db_name)
    return f'sqlite:///{db_path}'

# Import key components for easy access
try:
    from shared.models import (
        Base, Course, Lesson, LearningOutcome, 
        AssessmentFormat, Tool, LessonLearningOutcome
    )
    from pearson.cli.setup import DatabaseSetup
    from pearson.cli.course_injector import CourseInjector
    from pearson.web import web_bp # create_app
except ImportError as e:
    print(f"Warning: Could not import all modules: {e}")
    # These will be None if imports fail
    Base = Course = Lesson = LearningOutcome = None
    AssessmentFormat = Tool = LessonLearningOutcome = None
    DatabaseSetup = CourseInjector = None
    web_bp = None # create_app = 

# Convenience function to initialize everything
def init_app(config=None):
    """
    Initialize the application with given configuration.
    
    Args:
        config (dict): Configuration dictionary
        
    Returns:
        tuple: (app, db_setup) Flask app and DatabaseSetup instance
    """
    from flask import Flask
    from pearson.web import web_bp
    
    # Default configuration
    default_config = {
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
        'DATABASE_URL': os.environ.get('DATABASE_URL', get_database_url()),
        'DATA_DIR': str(get_data_dir()),
        'WTF_CSRF_ENABLED': True,
        'TESTING': False,
    }
    
    # Create app
    app = Flask(__name__)
    
    # Update config
    app.config.update(default_config)
    if config:
        app.config.update(config)
    
    # Register blueprint
    app.register_blueprint(web_bp)
    
    # Setup database
    from cli.setup import DatabaseSetup
    db_setup = DatabaseSetup(app.config['DATABASE_URL'])
    app.config['db_setup'] = db_setup

    print(f"📦 Pearson package initialized (root: {PROJECT_ROOT})")
    
    return app, db_setup