#!/usr/bin/env python3
"""
Run the Pearson web application.
Alternative to: python -m pearson --web
"""
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from pearson import init_app

if __name__ == '__main__':
    # Initialize app with configuration
    app, db_setup = init_app({
        'DEBUG': True,
        'TESTING': False,
    })
    
    # Store db_setup in app config (for routes)
    app.config['db_setup'] = db_setup
    
    print("Starting Pearson Course Management System...")
    print(f"Database: {app.config['DATABASE_URL']}")
    print("Open http://127.0.0.1:5000 in your browser")
    
    app.run(host='127.0.0.1', port=5000, debug=True)