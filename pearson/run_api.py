#!/usr/bin/env python3
"""
Educational Data Hub - API Server
"""
from pearson.api import app

def start_api(port=5000, debug=True):
    """Entry point for the API server used by main.py"""
    print("🚀 Starting Educational Data Hub API...")
    print(f"📍 http://localhost:{port}")
    print("📚 Available Endpoints:")
    print("   GET  /api/health")
    print("   GET  /api/courses") 
    print("   GET  /api/courses/<id>")
    
    app.run(debug=debug, host='0.0.0.0', port=port)

# Keep this for backward compatibility if you run the file directly
if __name__ == '__main__':
    start_api()