from waitress import serve

from pearson import create_app

# Create the application instance using your factory
app = create_app({
    'DEBUG': False,
    'TESTING': False
})

if __name__ == '__main__':
    print("🚀 Pearson Production Server starting on http://0.0.0.0:5000")
    # 0.0.0.0 makes the site accessible from other devices on your local network
    serve(app, host='0.0.0.0', port=5000, threads=4)