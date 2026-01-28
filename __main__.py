"""
Main entry point for the Pearson package.
Allows running: python -m pearson
"""
import sys
import argparse
from pearson import init_app, get_database_url

def main():
    """Main entry point for command-line execution."""
    parser = argparse.ArgumentParser(description='Pearson Course Management System')
    parser.add_argument('--web', action='store_true', help='Start web server')
    parser.add_argument('--host', default='127.0.0.1', help='Web server host')
    parser.add_argument('--port', type=int, default=5000, help='Web server port')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--init-db', action='store_true', help='Initialize database')
    
    args = parser.parse_args()
    
    if args.init_db:
        from cli.setup import DatabaseSetup
        db_url = get_database_url()
        print(f"Initializing database at {db_url}")
        db_setup = DatabaseSetup(db_url)
        print("Database initialized successfully!")
    
    if args.web:
        app, _ = init_app({
            'DEBUG': args.debug,
            'TESTING': args.debug,
        })
        print(f"Starting web server at http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=args.debug)
    
    if not (args.web or args.init_db):
        parser.print_help()

if __name__ == '__main__':
    main()