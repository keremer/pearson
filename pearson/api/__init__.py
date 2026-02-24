"""
Educational Data Hub - REST API (Pure Flask)
"""
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

from pearson.api.webhooks import init_webhook_routes
init_webhook_routes(app)

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'active', 
        'service': 'Educational Data Hub API',
        'version': '1.0'
    })

# Import and register routes
try:
    from api.courses import init_course_routes
    init_course_routes(app)
    print("✅ Course routes registered")
except ImportError as e:
    print(f"⚠️  Could not load course routes: {e}")