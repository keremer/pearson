import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from waitress import serve
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# ==============================================================================
# 0. ENCODING FIX: Prevent Windows cp1254 emoji crashes
# ==============================================================================
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')  # type: ignore
    
# 1. SETUP PATHS & ENVIRONMENT FIRST
# Get the directory where serve.py lives (Project Root)
basedir = Path(__file__).parent.absolute()
if str(basedir) not in sys.path:
    sys.path.insert(0, str(basedir))

# Explicitly load .env using the absolute path to bypass IIS directory confusion
load_dotenv(basedir / '.env')

# 2. IMPORT AND CREATE APP
# Now that paths and env vars are loaded, it is safe to import and create the app
from crminaec import create_app

# Read the environment variable (Defaults to production if running locally)
env = os.environ.get('FLASK_ENV', 'production')

# Pass the environment to the factory!
app = create_app(config_name=env)

# 3. IIS MIDDLEWARE SETUP
# Handle sub-directory hosting in IIS (e.g., if hosted at domain.com/crminaec)
script_name = os.environ.get('SCRIPT_NAME', '')
if script_name:
    # Wrap the Flask app to handle the URL prefix natively
    # We assign it to 'application' as that is the standard WSGI naming convention
    application = DispatcherMiddleware(app.wsgi_app, {script_name: app.wsgi_app})
else:
    application = app

if __name__ == "__main__":
    # 4. PORT BINDING
    # IIS dynamically assigns a port via the 'PORT' environment variable.
    # We MUST use this port or the 502.3 Bad Gateway error will persist.
    port = int(os.environ.get('PORT', 5000))
    
    print(f"🚀 crminaec Production Server Starting")
    print(f"📍 Root Directory: {basedir}")
    print(f"🌐 Listening on: http://127.0.0.1:{port}")
    if script_name:
        print(f"🔗 Hosted under script name: {script_name}")
    
    # 5. EXECUTE WAITRESS
    # Serve the 'application' (which handles the middleware wrapping if needed)
    serve(application, host='127.0.0.1', port=port, threads=4)