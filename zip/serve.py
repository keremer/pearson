import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from waitress import serve

from portal.main import app

script_name = os.environ.get('SCRIPT_NAME', '')
if script_name:
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    app = DispatcherMiddleware(app, {script_name: app})

# 1. SETUP PATHS
# Get the directory where serve.py lives (C:\GitHub\pythonapps\crminaec)
basedir = Path(__file__).parent.absolute()
# Ensure the project root is in the system path so 'crminaec' can be imported
sys.path.append(str(basedir))

# 2. LOAD ENVIRONMENT
# Explicitly load .env using the absolute path to bypass IIS directory confusion
load_dotenv(basedir / '.env')

# 3. IMPORT APP
# Import after paths are set to ensure internal relative imports don't fail
# Test if the manager is alive
if hasattr(app, 'interop_manager'):
    print("✅ Interop Manager attached and type-hinted.")
    
if __name__ == "__main__":
    # 4. PORT BINDING
    # IIS dynamically assigns a port via the 'PORT' environment variable.
    # We MUST use this port or the 502.3 Bad Gateway error will persist.
    port = int(os.environ.get('PORT', 5000))
    
    print(f"🚀 crminaec Production Server Starting")
    print(f"📍 Root Directory: {basedir}")
    print(f"🌐 Listening on: http://127.0.0.1:{port}")
    
    # 5. EXECUTE WAITRESS
    # 'app' is your Flask instance from crminaec.main
    serve(app, host='127.0.0.1', port=port, threads=4)