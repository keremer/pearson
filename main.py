import sys
import os
import argparse
from pathlib import Path

# --- GLOBAL PATH FIX ---
# This ensures that 'import pearson' and absolute imports like 'from web.routes' 
# work regardless of which subfolder you are in.
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

    #print(f"📁 Project structure:")
    #print(f"   Script location: {SCRIPT_DIR}")
    #print(f"   Project root: {PROJECT_ROOT}")
    print(f"   Python path includes: {sys.path[0]}")

def run_web_mode():
    """Logic to launch the Flask Web Server"""
    print("🖥️  Launching Web Interface...")
    try:
        from pearson.run_web import create_app
        app = create_app()
        port = int(os.environ.get('PORT', 5000))
        # Ensure debug mode is handled via config as per your run_web logic
        app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', True))
    except ImportError as e:
        print(f"❌ Web Import Error: {e}. Ensure 'flask' is installed.")

def run_cli_mode():
    """Logic to launch the CLI"""
    print("🚀 Launching CLI...")
    # This points to your run_cli entry point
    try:
        from pearson.run_cli import main as start_cli 
        start_cli()
    except ImportError as e:
        print(f"❌ CLI Import Error: {e}")

def run_api_mode():
    """Logic to launch the REST API (FastAPI/Flask-RESTful)"""
    print("🌐 Launching API...")
    try:
        # Assuming run_api has an 'app' object or start function
        from pearson.run_api import start_api
        start_api()
    except ImportError as e:
        print(f"❌ API Import Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Pearson Project Unified Entry Point")
    parser.add_argument('mode', choices=['cli', 'api', 'web'], 
                        help="Choose the interface to launch")
    
    # Optional: Allow passing port or env via CLI
    parser.add_argument('--port', type=int, help="Override default port")

    args = parser.parse_args()

    if args.port:
        os.environ['PORT'] = str(args.port)

    if args.mode == 'web':
        run_web_mode()
    elif args.mode == 'cli':
        run_cli_mode()
    elif args.mode == 'api':
        run_api_mode()

if __name__ == "__main__":
    main()