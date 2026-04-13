#!/usr/bin/env python3
"""
crminaec Management Portal - Unified Entry Point
Uses Click for CLI management with Lazy Initialization for performance
"""
import sys
from pathlib import Path
from typing import List, Optional

import click

from crminaec import create_app
from import_legacy import run_import

# Add project root to path for consistent imports
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(version='1.0.0', prog_name='crminaec Portal')
def cli():
    """crminaec Platform - Unified Management CLI"""
    pass

# =====================================================================
# 🌐 WEB & API SERVERS
# =====================================================================

@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=5000, help='Port to listen on')
@click.option('--debug/--no-debug', default=True, help='Enable debug mode')
def web(host: str, port: int, debug: bool):
    """Start the Unified Web Interface"""
    from crminaec import create_app
    app = create_app()

    print(app.url_map)
    click.echo(f"🌐 Starting crminaec Web Interface...")
    click.echo(f"   URL: http://{host}:{port}")
    click.echo(f"   Debug: {debug}")
    
    app.run(host=host, port=port, debug=debug)

@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=8000, help='Port to listen on')
@click.option('--debug/--no-debug', default=True, help='Enable debug mode')
def api(host: str, port: int, debug: bool):
    """Start the standalone REST API server"""
    try:
        from crminaec.run_api import start_api
        click.echo(f"🚀 Starting crminaec REST API...")
        click.echo(f"   URL: http://{host}:{port}/api")
        
        start_api(port=port, debug=debug)
    except ImportError as e:
        click.echo(f"❌ API module not available: {e}")
        sys.exit(1)

# =====================================================================
# 🗄️ DATABASE MANAGEMENT
# =====================================================================

@cli.command()
@click.option('--reset', is_flag=True, help='Reset database before setup')
@click.option('--sample-data', is_flag=True, help='Add sample data')
def setup(reset: bool, sample_data: bool):
    """Initialize or reset the database"""
    from crminaec import create_app
    from crminaec.core.database import DatabaseSetup
    
    app = create_app()
    db_setup = DatabaseSetup(app)
    
    if reset:
        click.confirm('⚠️ This will wipe all data. Continue?', abort=True)
        click.echo("🗑️  Dropping database tables...")
        db_setup.drop_tables()
    
    click.echo("🗄️  Creating database tables...")
    db_setup.create_tables()
    
    if sample_data:
        click.echo("📝 Creating sample data...")
        db_setup.create_sample_data()
    
    db_setup.list_summary()
    click.echo("✅ Setup completed successfully!")

@cli.command()
@click.argument('model_name', type=click.Choice([
    'course', 'lesson', 'learningoutcome', 'tool', 'assessment', 
    'party', 'order', 'item', 'composition'  # <-- Added EMEK models here
]))
@click.option('--count', type=int, default=5, help='Number of items to show')
def inspect(model_name: str, count: int):
    """Inspect database models and their structure"""
    from sqlalchemy import inspect as sa_inspect

    from crminaec import create_app
    from crminaec.core.models import (AssessmentFormat, Course,
                                      LearningOutcome, Lesson, Order, Party,
                                      Tool, db)
    # Ensure EMEK models are imported
    from crminaec.platforms.emek import models as emek_models
    
    app = create_app()
    
    model_map = {
        'course': Course, 'lesson': Lesson, 'learningoutcome': LearningOutcome,
        'tool': Tool, 'assessment': AssessmentFormat, 'party': Party, 'order': Order,
        'item': emek_models.Item,                       # <-- Mapped 'item'
        'composition': emek_models.ItemComposition      # <-- Mapped 'composition'
    }
    
    # --- PYLANCE GUARD CLAUSE ---
    model_class = model_map.get(model_name)
    if model_class is None:
        click.echo(f"❌ Unknown model: {model_name}")
        return
    # ----------------------------
    
    with app.app_context():
        try:
            inspector = sa_inspect(db.engine)
            
            # Pylance now knows model_class is absolutely a Model, not None
            table_name = str(model_class.__tablename__) 
            columns = inspector.get_columns(table_name)
            
            click.echo(f"\n📊 Table: {table_name}")
            click.echo("=" * 40)
            click.echo("Columns:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col['default'] else ""
                click.echo(f"  - {col['name']}: {col['type']} {nullable}{default}")
            
            items = db.session.query(model_class).limit(count).all()
            
            click.echo(f"\n📝 Sample Data (first {count} items):")
            if items:
                for i, item in enumerate(items, 1):
                    click.echo(f"\n  {i}. {item}")
            else:
                click.echo("  No data found")
                
        except Exception as e:
            click.echo(f"❌ Error inspecting model: {e}")

# =====================================================================
# 🎓 CONTENT INJECTION & GENERATION
# =====================================================================

@cli.command()
@click.argument('file', type=click.Path(exists=True))
def inject(file: str):
    """Inject a comprehensive course from markdown/file"""
    from crminaec.cli.course_injector import CourseInjector
    
    injector = CourseInjector()
    success = injector.inject_comprehensive_course(file)
    
    if success:
        click.echo("✅ Course injected successfully!")
    else:
        click.echo("❌ Failed to inject course")
        sys.exit(1)

@cli.command()
@click.option('--course-id', type=int, help='Filter by course ID')
@click.option('--lesson-id', type=int, help='Filter by lesson ID')
@click.option('--format', 'output_format', multiple=True, help='Output format')
@click.option('--template', 'template_name', multiple=True, help='Template to use')
@click.option('--batch', is_flag=True, help='Process all items')
@click.option('--output-dir', type=click.Path(), default='output', help='Output directory')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def generate(course_id, lesson_id, output_format, template_name, batch, output_dir, verbose):
    """Generate course materials (PDF, Markdown)"""
    from crminaec import get_database_url
    from crminaec.cli.commands import CLICommands
    
    formats = list(output_format) if output_format else None
    templates = list(template_name) if template_name else None
    
    cli_cmds = CLICommands(database_url=get_database_url(), output_dir=output_dir, verbose=verbose)
    success = cli_cmds.generate_materials(
        course_id=course_id, lesson_id=lesson_id, formats=formats, templates=templates, batch=batch
    )
    
    if success:
        click.echo("✅ Materials generated successfully!")
    else:
        sys.exit(1)

@cli.command()
@click.argument('what', type=click.Choice(['courses', 'lessons', 'outcomes', 'tools', 'formats', 'all']))
@click.option('--course-id', type=int, help='Filter by course ID')
@click.option('--detailed', '-d', is_flag=True, help='Show detailed information')
def list_items(what: str, course_id: Optional[int], detailed: bool):
    """List database items"""
    from crminaec import get_database_url
    from crminaec.cli.commands import CLICommands
    
    cli_cmds = CLICommands(database_url=get_database_url(), output_dir='output', verbose=detailed)
    if not cli_cmds.list_items(what=what, course_id=course_id, detailed=detailed):
        sys.exit(1)

@cli.command()
@click.option('--course-id', type=int, help='Filter by course ID')
@click.option('--format', 'export_format', type=click.Choice(['json', 'csv', 'excel', 'md', 'yaml']), default='json')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
def export(course_id: int, export_format: str, output: Optional[str]):
    """Export course data"""
    from crminaec import get_database_url
    from crminaec.cli.commands import CLICommands
    
    cli_cmds = CLICommands(database_url=get_database_url(), output_dir='output', verbose=True)
    if cli_cmds.export_data(course_id=course_id, format=export_format, output=output):
        click.echo(f"✅ Data exported successfully in {export_format} format!")
    else:
        sys.exit(1)

# =====================================================================
# 🛠️ UTILITIES & DIAGNOSTICS
# =====================================================================

@cli.command()
def check():
    """Check system health and configuration"""
    from crminaec import create_app, get_database_url
    click.echo("🔍 crminaec System Check")
    click.echo("=" * 40)
    click.echo(f"Python: {sys.version.split()[0]}")
    click.echo(f"Project Root: {PROJECT_ROOT}")
    
    db_url = get_database_url()
    click.echo(f"Database URL: {db_url}")
    
    try:
        app = create_app()
        click.echo("Flask app creation: ✓")
        blueprints = ', '.join(app.blueprints.keys()) if app.blueprints else "None"
        click.echo(f"Registered blueprints: {blueprints}")
    except Exception as e:
        click.echo(f"Flask app creation: ✗ ({e})")
    
    click.echo("=" * 40)
    click.echo("✅ System check completed")

@cli.command()
def tree():
    """Generate a Markdown-ready folder tree with wildcard ignoring"""
    # Notice: No Flask or DB imports here! It runs instantly.
    IGNORE_PATTERNS = [
        '.*',           # Ignores .git, .vscode, .venv, .idea, etc.
        '__pycache__', 
        '*.egg-info', 
        'venv', 
        'env', 
        'node_modules',
        'instance',
        '*.sqlite3', 
        '*.db',
        '*.html',
        '*.md',
        '*.doc*',
        '*.png',
        '*.log',
        '*.zip',
    ]

    def should_ignore(path):
        return any(path.match(pattern) for pattern in IGNORE_PATTERNS)

    def _build_tree(dir_path, prefix=""):
        paths = sorted([p for p in dir_path.iterdir() if not should_ignore(p)])
        output = ""
        
        for index, path in enumerate(paths):
            is_last = index == (len(paths) - 1)
            connector = "└── " if is_last else "├── "
            
            output += f"{prefix}{connector}{path.name}\n"
            
            if path.is_dir():
                extension = "    " if is_last else "│   "
                output += _build_tree(path, prefix + extension)
                
        return output

    click.echo("```text")
    click.echo(f"{PROJECT_ROOT.name}/")
    click.echo(_build_tree(PROJECT_ROOT), nl=False)
    click.echo("```")

# =====================================================================
# 🎓 CONTENT INJECTION & BOM
# =====================================================================

@cli.command()
def migrate():
    """🚀 Runs the new Master Pipeline for Legacy Data Migration"""
    from crminaec import create_app, db
    from migration import run_master_import
    
    app = create_app()
    
    click.echo("=========================================")
    click.echo("🚀 INITIALIZING LEGACY DATA MIGRATION...")
    click.echo("=========================================")
    
    # We MUST push the app context so SQLAlchemy knows which database to talk to
    with app.app_context():
        # (Optional) Wipe the slate clean before importing if you want a fresh start
        # db.drop_all()
        # db.create_all()
        
        # Run the magic
        run_master_import()
        
    click.echo("=========================================")
    click.echo("✅ MIGRATION COMPLETE. Exiting safely.")
    click.echo("=========================================")

@cli.command()
@click.argument('data_dir', default='legacy_data', type=click.Path(exists=True))
def import_legacy(data_dir):
    """Imports MS Access CSV dumps into the EMEK BoM engine."""
    app = create_app()
    run_import(app, data_dir)

from clean_legacy import run_cleanup


@cli.command()
def clean_legacy():
    """Fixes semantic issues, deduplicates names, and extracts DNA."""
    app = create_app()
    run_cleanup(app)
       
# Attach the external report command group
try:
    from crminaec.cli.report_commands import report
    cli.add_command(report)
except ImportError:
    pass

if __name__ == '__main__':
    cli()