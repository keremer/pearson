#!/usr/bin/env python3
"""
Pearson Course Management System - Unified Entry Point
Uses Click for CLI management
"""
import os
import sys
from pathlib import Path
from typing import Optional, List

# Add project root to path for consistent imports
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
from pearson.cli.report_commands import report

import click
from flask import Flask

# Now import from the pearson package
from pearson import create_app, get_database_url
from pearson.cli import CLICommands, DatabaseSetup, CourseInjector  # Fixed imports


@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(version='1.0.0', prog_name='Pearson Course Manager')
def cli():
    """Pearson Course Management System - Unified CLI"""
    pass


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=5000, help='Port to listen on')
@click.option('--debug/--no-debug', default=True, help='Enable debug mode')
def web(host: str, port: int, debug: bool):
    """Start the web interface"""
    app = create_app({
        'DEBUG': debug,
        'TESTING': debug,
    })
    
    click.echo(f"🌐 Starting Pearson Web Interface...")
    click.echo(f"   URL: http://{host}:{port}")
    click.echo(f"   Debug: {debug}")
    
    app.run(host=host, port=port, debug=debug)
    
cli.add_command(report)

@cli.command()
@click.option('--database', default=None, help='Database URL (overrides default)')
@click.option('--reset', is_flag=True, help='Reset database before setup')
@click.option('--sample-data', is_flag=True, help='Add sample data')
def setup(database: Optional[str], reset: bool, sample_data: bool):
    """Initialize or reset the database"""
    db_url = database or get_database_url()
    db_setup = DatabaseSetup(db_url)
    
    if reset:
        click.echo("🗑️  Dropping database tables...")
        db_setup.drop_tables()
    
    click.echo("🗄️  Creating database tables...")
    db_setup.create_tables()
    
    if sample_data:
        click.echo("📝 Creating sample data...")
        db_setup.create_sample_data()
    
    click.echo("📊 Listing courses...")
    db_setup.list_courses()
    
    click.echo("✅ Setup completed successfully!")


@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('--database', default=None, help='Database URL (overrides default)')
def inject(file: str, database: Optional[str]):
    """Inject a comprehensive course from file"""
    db_url = database or get_database_url()
    injector = CourseInjector(db_url)
    success = injector.inject_comprehensive_course(file)
    
    if success:
        click.echo("✅ Course injected successfully!")
    else:
        click.echo("❌ Failed to inject course")
        sys.exit(1)


@cli.command()
@click.option('--course-id', type=int, help='Filter by course ID')
@click.option('--lesson-id', type=int, help='Filter by lesson ID')
@click.option('--format', 'output_format', multiple=True, help='Output format (multiple allowed)')
@click.option('--template', 'template_name', multiple=True, help='Template to use (multiple allowed)')
@click.option('--batch', is_flag=True, help='Process all items')
@click.option('--output-dir', type=click.Path(), default='output', help='Output directory')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def generate(
    course_id: Optional[int], 
    lesson_id: Optional[int], 
    output_format: tuple, 
    template_name: tuple, 
    batch: bool, 
    output_dir: str, 
    verbose: bool
):
    """Generate course materials"""
    # Convert tuples to lists or use None
    formats: Optional[List[str]] = list(output_format) if output_format else None
    templates: Optional[List[str]] = list(template_name) if template_name else None
    
    cli_cmds = CLICommands(
        database_url=get_database_url(),
        output_dir=output_dir,
        verbose=verbose
    )
    
    success = cli_cmds.generate_materials(
        course_id=course_id,
        lesson_id=lesson_id,
        formats=formats,
        templates=templates,
        batch=batch
    )
    
    if success:
        click.echo("✅ Materials generated successfully!")
    else:
        click.echo("❌ Failed to generate materials")
        sys.exit(1)


@cli.command()
@click.argument('what', type=click.Choice(['courses', 'lessons', 'outcomes', 'tools', 'formats', 'all']))
@click.option('--course-id', type=int, help='Filter by course ID')
@click.option('--detailed', '-d', is_flag=True, help='Show detailed information')
def list_items(what: str, course_id: Optional[int], detailed: bool):
    """List database items"""
    cli_cmds = CLICommands(
        database_url=get_database_url(),
        output_dir='output',
        verbose=detailed
    )
    
    # Now list_items should exist in CLICommands
    success = cli_cmds.list_items(
        what=what,
        course_id=course_id,
        detailed=detailed
    )
    
    if not success:
        sys.exit(1)


@cli.command()
@click.option('--course-id', type=int, help='Filter by course ID')
@click.option('--format', 'export_format', type=click.Choice(['json', 'csv', 'excel', 'md', 'yaml']), 
              default='json', help='Export format')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
def export(course_id: int, export_format: str, output: Optional[str]):
    """Export course data"""
    cli_cmds = CLICommands(
        database_url=get_database_url(),
        output_dir='output',
        verbose=True
    )
    
    # Now export_data should exist in CLICommands
    success = cli_cmds.export_data(
        course_id=course_id,
        format=export_format,
        output=output
    )
    
    if success:
        click.echo(f"✅ Data exported successfully in {export_format} format!")
    else:
        click.echo("❌ Failed to export data")
        sys.exit(1)

# ... rest of main.py remains the same ...

@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=8000, help='Port to listen on')
@click.option('--debug/--no-debug', default=True, help='Enable debug mode')
def api(host: str, port: int, debug: bool):
    """Start the REST API server"""
    try:
        from pearson.run_api import start_api
        click.echo(f"🚀 Starting Pearson REST API...")
        click.echo(f"   URL: http://{host}:{port}/api")
        click.echo(f"   Debug: {debug}")
        
        start_api(port=port, debug=debug)
    except ImportError as e:
        click.echo(f"❌ API module not available: {e}")
        click.echo("Install API dependencies: pip install 'pearson-course-manager[api]'")
        sys.exit(1)


@cli.command()
@click.option('--db-name', default='courses.db', help='Database name')
def check(db_name: str):
    """Check system health and configuration"""
    click.echo("🔍 Pearson System Check")
    click.echo("=" * 40)
    
    # Check Python version
    click.echo(f"Python: {sys.version}")
    
    # Check project structure
    click.echo(f"Project Root: {PROJECT_ROOT}")
    
    # Check database
    db_url = get_database_url(db_name)
    click.echo(f"Database URL: {db_url}")
    
    # Check if database exists
    db_path = PROJECT_ROOT / 'data' / db_name
    if db_path.exists():
        click.echo(f"Database exists: Yes ({db_path.stat().st_size} bytes)")
    else:
        click.echo("Database exists: No")
    
    # Try to create app
    try:
        app = create_app()
        click.echo("Flask app creation: ✓")
        
        # Check blueprints
        if app.blueprints:
            click.echo(f"Registered blueprints: {', '.join(app.blueprints.keys())}")
        else:
            click.echo("Registered blueprints: None")
            
    except Exception as e:
        click.echo(f"Flask app creation: ✗ ({e})")
    
    click.echo("=" * 40)
    click.echo("✅ System check completed")


@cli.command()
@click.argument('model_name', type=click.Choice(['course', 'lesson', 'learningoutcome', 'tool', 'assessment']))
@click.option('--count', type=int, default=5, help='Number of items to show')
def inspect(model_name: str, count: int):
    """Inspect database models and their structure"""
    try:
        from pearson.models import Base
        from sqlalchemy import inspect as sa_inspect, create_engine
        
        # Create a database engine
        engine = create_engine(get_database_url())
        
        inspector = sa_inspect(engine)
        
        if model_name == 'course':
            from pearson.models import Course
            table_name = Course.__tablename__
            model_class = Course
        elif model_name == 'lesson':
            from pearson.models import Lesson
            table_name = Lesson.__tablename__
            model_class = Lesson
        elif model_name == 'learningoutcome':
            from pearson.models import LearningOutcome
            table_name = LearningOutcome.__tablename__
            model_class = LearningOutcome
        elif model_name == 'tool':
            from pearson.models import Tool
            table_name = Tool.__tablename__
            model_class = Tool
        elif model_name == 'assessment':
            from pearson.models import AssessmentFormat
            table_name = AssessmentFormat.__tablename__
            model_class = AssessmentFormat
        else:
            click.echo(f"❌ Unknown model: {model_name}")
            return
        
        # Get table columns
        columns = inspector.get_columns(table_name)
        
        click.echo(f"\n📊 Table: {table_name}")
        click.echo("=" * 40)
        click.echo("Columns:")
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            default = f" DEFAULT {col['default']}" if col['default'] else ""
            click.echo(f"  - {col['name']}: {col['type']} {nullable}{default}")
        
        # Get sample data
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        
        items = session.query(model_class).limit(count).all()
        
        click.echo(f"\n📝 Sample Data (first {count} items):")
        if items:
            for i, item in enumerate(items, 1):
                click.echo(f"\n  {i}. {item}")
        else:
            click.echo("  No data found")
        
        session.close()
        
    except Exception as e:
        click.echo(f"❌ Error inspecting model: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    cli()