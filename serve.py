import os
from pathlib import Path

from dotenv import load_dotenv
from waitress import serve

from pearson import create_app

# Get the directory where THIS file lives
basedir = Path(__file__).parent.absolute()

# Explicitly load the .env using the absolute path
load_dotenv(os.path.join(basedir, '.env'))

# Create the application instance using your factory
app = create_app({
    'DEBUG': False,
    'TESTING': False
})

if __name__ == '__main__':
    # Get port from environment variable (set by IIS) or default to 8080
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Pearson Production Server starting on http://0.0.0.0:{port}")
    # 0.0.0.0 makes the site accessible from other devices on your local network
    serve(app, host='0.0.0.0', port=port, threads=4)