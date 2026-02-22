#!/usr/bin/env python3
"""
Run the Pearson web application.
Alternative to: python -m pearson --web
"""
import sys
from pathlib import Path
from typing import Dict, Any

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

from pearson import init_app

if __name__ == '__main__':
    # Initialize app with configuration (using init_app for backward compatibility)
    config: Dict[str, Any] = {
        'DEBUG': True,
        'TESTING': False,
    }
    
    # Use init_app for backward compatibility (returns tuple)
    app, db_setup = init_app(config)
    
    # Store db_setup in app config (for routes)
    app.config['db_setup'] = db_setup
    
    print("Starting Pearson Course Management System...")
    print(f"Database: {app.config['DATABASE_URL']}")
    print("Open http://127.0.0.1:5000 in your browser")
    
    app.run(host='127.0.0.1', port=5000, debug=True)