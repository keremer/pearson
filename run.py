#!/usr/bin/env python3
import os
import sys
import click
from pathlib import Path
from typing import List, Optional

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from portal import create_app, get_database_url

# Import your CLI logic classes (Ensure these paths are correct in your project)
# These usually live in portal/core/cli_logic.py or similar
from .cli import CLICommands, CourseInjector, DatabaseSetup
# from portal.core.report_commands import report # If you have a separate report module

app = create_app()

@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(version='1.0.0', prog_name='crminaec Portal')
def cli():
    """crminaec Platform - Unified Management CLI"""
    pass

# --- WEB COMMAND ---
@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=5000, help='Port to listen on')
@click.option('--debug/--no-debug', default=True, help='Enable debug mode')
def web(host, port, debug):
    """Start the Unified Web Interface (Pearson + Arkhon)"""
    click.echo(f"🌐 Starting crminaec Web Interface...")
    click.echo(f"   URL: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)

# --- SETUP COMMAND ---
@cli.command()
@click.option('--database', default=None, help='Database URL override')
@click.option('--reset', is_flag=True, help='Reset database before setup')
@click.option('--sample-data', is_flag=True, help='Add sample data')
def setup(database, reset, sample_data):
    """Initialize or reset the database"""
    db_url = database or get_database_url()
    db_setup = DatabaseSetup(db_url)
    
    if reset:
        click.confirm('This will wipe all data. Continue?', abort=True)
        db_setup.drop_tables()
    
    db_setup.create_tables()
    if sample_data:
        db_setup.create_sample_data()
    click.echo("✅ Setup completed successfully!")

# --- INJECT COMMAND ---
@cli.command()
@click.argument('file', type=click.Path(exists=True))
def inject(file):
    """Inject a comprehensive course from markdown/file"""
    injector = CourseInjector(get_database_url())
    if injector.inject_comprehensive_course(file):
        click.echo("✅ Course injected successfully!")
    else:
        click.echo("❌ Injection failed.")

# --- GENERATE COMMAND ---
@cli.command()
@click.option('--course-id', type=int)
@click.option('--output-dir', default='output')
def generate(course_id, output_dir):
    """Generate course materials/documents"""
    cli_cmds = CLICommands(database_url=get_database_url(), output_dir=output_dir)
    if cli_cmds.generate_materials(course_id=course_id, batch=(not course_id)):
        click.echo(f"✅ Materials generated in {output_dir}")

# --- CHECK/HEALTH COMMAND ---
@cli.command()
def check():
    """Check system health and folder structure"""
    click.echo("🔍 crminaec System Check")
    click.echo(f"Project Root: {PROJECT_ROOT}")
    click.echo(f"Database: {get_database_url()}")
    # Add logic here to check if client_secret.json exists, etc.
    click.echo("✅ Check complete.")

if __name__ == '__main__':
    cli()