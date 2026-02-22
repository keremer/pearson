#!/usr/bin/env python3
"""
Course Automation System - Main CLI Entry Point
UPDATED FOR NEW PROJECT STRUCTURE
"""

import sys
import os
from pathlib import Path

# Add the current directory to Python path for package imports
sys.path.insert(0, str(Path(__file__).parent))

from cli.argparse_setup import setup_argparse

def main():
    """Main CLI entry point"""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Handle setup command separately (no CLICommands needed)
    if args.command == 'setup':
        from cli.setup import DatabaseSetup
        db_setup = DatabaseSetup(args.database)
        
        if args.reset:
            print("🗑️  Dropping database tables...")
            db_setup.drop_database()
        
        print("🗄️  Creating database tables...")
        db_setup.create_database()
        
        if args.sample_data:
            print("📝 Creating sample data...")
            db_setup.create_sample_data()
            
        print("📊 Listing courses...")
        db_setup.list_courses()
        
        print("✅ Setup completed successfully!")
        return
    
    # Handle inject command separately
    if args.command == 'inject':
        from cli.course_injector import CourseInjector
        injector = CourseInjector(args.database or 'sqlite:///courses.db')
        success = injector.inject_comprehensive_course(args.file)
        sys.exit(0 if success else 1)
    
    if not args.command:
        parser.print_help()
        return
    
    # For other commands, initialize CLICommands
    from cli.commands import CLICommands
    cli = CLICommands(
        database_url=args.database,
        output_dir=args.output_dir,
        verbose=args.verbose
    )
    
    # Execute command
    try:
        if args.command == 'generate':
            success = cli.generate_materials(
                course_id=args.course_id,
                lesson_id=args.lesson_id,
                formats=args.format,
                templates=args.template,
                batch=args.batch
            )
            sys.exit(0 if success else 1)
            
        elif args.command == 'list':
            success = cli.list_items(
                what=args.what,
                course_id=args.course_id,
                detailed=args.detailed
            )
            sys.exit(0 if success else 1)
            
        elif args.command == 'export':
            success = cli.export_data(
                course_id=args.course_id,
                format=args.format,
                output=args.output
            )
            sys.exit(0 if success else 1)
            
        elif args.command == 'batch':
            success = cli.generate_materials(
                formats=args.format,
                templates=args.template,
                batch=True
            )
            sys.exit(0 if success else 1)
            
        elif args.command == 'add':
            print("🚧 Add command coming soon!")
            # Will be implemented later
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()