#!/usr/bin/env python3
"""
crminaec Management Portal - Unified Entry Point
Consolidated CLI for Database, Content, and Server Management
"""
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import click
import pandas as pd
from sqlalchemy.exc import IntegrityError

# =====================================================================
# 🛡️ THE SAFETY LOCK: Force run.py to ALWAYS use Development config
# =====================================================================
os.environ['FLASK_ENV'] = 'development'

# 🚨 THE NEW FIX: Tell Authlib that HTTP is okay for local testing
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'

# Add project root to path for consistent imports
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crminaec import __about__, create_app

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(version=__about__.__version__, prog_name='crminaec Portal')
def cli():
    """crminaec Platform - Unified Management CLI"""
    pass

# =====================================================================
# 🌐 SERVERS
# =====================================================================

@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=5000, help='Port to listen on')
@click.option('--debug/--no-debug', default=True, help='Enable debug mode')
def web(host: str, port: int, debug: bool):
    """Start the Unified Web & API Server (Waitress / Werkzeug)"""
    app = create_app()

    click.echo(f"🌐 Starting crminaec Ecosystem...")
    click.echo(f"   URL: http://{host}:{port}")
    click.echo(f"   Environment: {'Debug' if debug else 'Production'}")
    
    app.run(host=host, port=port, debug=debug)

# =====================================================================
# 🗄️ DATABASE MANAGEMENT
# =====================================================================

@cli.group()
def db():
    """Database migration commands (Alembic wrapper)."""
    pass

@db.command()
def init():
    """Initializes the migrations directory."""
    click.echo("🚀 Initializing database migrations...")
    os.system('flask --app crminaec db init')

@db.command()
@click.option('-m', '--message', required=True, help='Migration message.')
def migrate(message):
    """Generates a new migration file."""
    click.echo(f"📝 Generating migration: {message}")
    os.system(f'flask --app crminaec db migrate -m "{message}"')

@db.command()
def upgrade():
    """Applies the latest migration to the database."""
    click.echo("⏫ Applying database migrations...")
    os.system('flask --app crminaec db upgrade')

@db.command()
def downgrade():
    """Reverts the last migration."""
    click.echo("⏬ Reverting last migration...")
    os.system('flask --app crminaec db downgrade')

@cli.command()
@click.option('--reset', is_flag=True, help='Reset database before setup')
@click.option('--sample-data', is_flag=True, help='Add sample data')
def setup(reset: bool, sample_data: bool):
    """Initialize or reset the database"""
    from crminaec.core.database import DatabaseSetup
    
    app = create_app()
    db_setup = DatabaseSetup(app)
    
    if reset:
        click.confirm('⚠️ This will wipe all data. Continue?', abort=True)
        db_setup.drop_tables()
    
    db_setup.create_tables()
    
    if sample_data:
        db_setup.create_sample_data()
    
    db_setup.list_summary()
    click.echo("✅ Setup completed successfully!")

@cli.command()
@click.argument('model_name', type=click.Choice([
    'party', 'order', 'item', 'composition', 'price_record'
]))
@click.option('--count', type=int, default=5, help='Number of items to show')
def inspect(model_name: str, count: int):
    """Inspect database models and their structure"""
    from typing import Any, Type

    from sqlalchemy import inspect as sa_inspect

    from crminaec.core.models import Order, Party, PriceRecord, db
    from crminaec.platforms.emek import models as emek_models

    app = create_app()
    
    # Mapping strings to actual classes
    model_map: dict[str, Any] = {
        'party': Party, 
        'order': Order, 
        'price_record': PriceRecord,
        'item': emek_models.Item,
        'composition': emek_models.ItemComposition
    }
    
    # 1. Fetch from map
    model_class = model_map.get(model_name)
    
    # 2. THE GUARD: Explicitly prove to Pylance this isn't None
    if model_class is None:
        click.echo(f"❌ Unknown model: {model_name}")
        return

    with app.app_context():
        try:
            # 3. Use getattr or cast to satisfy Pylance
            # Pylance often chokes on .__tablename__ because it's a dynamic SQLAlchemy attribute
            table_name = getattr(model_class, '__tablename__', 'unknown_table')
            
            inspector = sa_inspect(db.engine)
            columns = inspector.get_columns(table_name)
            
            click.echo(f"\n📊 Table: {table_name}")
            click.echo("=" * 40)
            for col in columns:
                click.echo(f"  - {col['name']}: {col['type']}")
            
            # 4. Query using the narrowed model_class (SQLAlchemy 2.0)
            items = db.session.scalars(db.select(model_class).limit(count)).all()
            
            click.echo(f"\n📝 Sample Data (first {count}):")
            if items:
                for item in items:
                    click.echo(f"  - {item}")
            else:
                click.echo("  No data found.")
                
        except Exception as e:
            click.echo(f"❌ Error during inspection: {e}")

# =====================================================================
# 🛠️ UTILITIES
# =====================================================================

@cli.command()
def tree():
    """Generate a Markdown-ready folder tree"""
    IGNORE = {'.git', '.venv', '__pycache__', 'instance', '.vscode'}

    def _build_tree(dir_path, prefix=""):
        paths = sorted([p for p in dir_path.iterdir() if p.name not in IGNORE and not p.name.startswith('.')])
        output = ""
        for i, path in enumerate(paths):
            is_last = i == (len(paths) - 1)
            connector = "└── " if is_last else "├── "
            output += f"{prefix}{connector}{path.name}\n"
            if path.is_dir():
                output += _build_tree(path, prefix + ("    " if is_last else "│   "))
        return output

    click.echo(f"```text\n{PROJECT_ROOT.name}/\n{_build_tree(PROJECT_ROOT)}```")

# =====================================================================
# 📥 DATA IMPORT (EMEK Core)
# =====================================================================

@cli.command('importdata')
@click.argument('data_dir', default='.', type=click.Path(exists=True))
@click.option('--merge', is_flag=True, help="Merge duplicates instead of renaming")
def importdata(data_dir, merge):
    """Inject EMEK hierarchy and bulk import CSV data"""
    from crminaec.core.models import db
    from crminaec.platforms.emek.models import (Item, ItemComposition,
                                                PriceSource)

    app = create_app()
    with app.app_context():
        # Structural Root Injection
        click.echo("🌱 Verifying EMEK structural hierarchy...")
        # ---------------------------------------------------------
        # PART 1: INJECT ROOT FOLDERS
        # ---------------------------------------------------------
        click.echo("🌱 Checking and injecting structural hierarchy...")

        def create_node(code: str, name: str, parent: Optional[Item] = None) -> Item:
            folder = db.session.scalar(db.select(Item).filter_by(code=code))
            if not folder:
                folder = Item(**{'code': code, 'name': name, 'is_category': True, 'base_cost': 0.0})
                db.session.add(folder)
                db.session.flush()
            
            if parent:
                link = db.session.scalar(db.select(ItemComposition).filter_by(
                    parent_id=parent.item_id, child_id=folder.item_id
                ))
                if not link:
                    db.session.add(ItemComposition(**{
                        'parent_item': parent, 
                        'child_item': folder, 
                        'quantity': 1.0, 
                        'optional_attributes': {}
                    }))
                    db.session.flush()
                    
            return folder

        emek_root = create_node("EMEK", "EMEK Architecture")
        prj_dir = create_node("PRJ", "Projects & Installations", emek_root)
        edu_dir = create_node("EDU", "Academic & Curriculum", emek_root)
        rnd_dir = create_node("RND", "Research & Development", emek_root)
        lib_dir = create_node("LIB", "Libraries & Archives", emek_root)

        create_node("CRM", "crminaec Framework", rnd_dir)
        create_node("EDU-BAU", "Bauhaus Pedagogical Studies", rnd_dir)
        create_node("EDU-HND5", "Pearson HND5 Art & Design", edu_dir)
        create_node("EDU-CAS", "Course Automation System", edu_dir)
        create_node("EDU-LIB", "ArchNotes Repository", lib_dir)
        create_node("PRJ-INST01", "Mirror Star Prism Installation", prj_dir)

        db.session.commit()
        click.echo("✅ Organizational structure verified.")

        # ---------------------------------------------------------
        # PART 2: BULK IMPORT CSV DATA
        # ---------------------------------------------------------
        items_path = os.path.join(data_dir, 'items.csv')
        comps_path = os.path.join(data_dir, 'compositions.csv')

        if not os.path.exists(items_path) or not os.path.exists(comps_path):
            click.echo("⚠️ Warning: items.csv or compositions.csv not found. Skipping CSV import.")
            return

        click.echo("📦 Reading CSV files...")
        df_items = pd.read_csv(items_path).fillna('')
        df_comps = pd.read_csv(comps_path).fillna('')

        def parse_json(val_str):
            if not val_str: return {}
            try:
                val_str = str(val_str).replace('""', '"')
                return json.loads(val_str)
            except json.JSONDecodeError:
                return {}

        # --- DEDUPLICATION CACHE & MAPPING ---
        # Cache existing items to speed up lookups (Code -> ID, Name -> ID)
        existing_items = db.session.execute(db.select(Item.item_id, Item.code, Item.name)).all()
        code_to_id = {item.code: item.item_id for item in existing_items}
        name_to_id = {item.name: item.item_id for item in existing_items}
        
        # Translation dictionary: Maps CSV ID -> Target Database ID
        id_translation_map = {} 

        # IMPORT ITEMS
        mode_str = "MERGING" if merge else "RENAMING"
        click.echo(f"📥 Scanning {len(df_items)} items... (Mode: {mode_str} Duplicates)")
        
        try:
            for _, row in df_items.iterrows():
                csv_id = int(row['item_id'])
                # CIQ VALIDATION: Enforce strict formatting on import
                raw_code = str(row['code']).strip().upper()
                raw_name = str(row['name']).strip()
                
                # 1. Skip if the exact ID already exists (e.g. re-running the script)
                if db.session.get(Item, csv_id):
                    id_translation_map[csv_id] = csv_id
                    continue

                # 2. Check for Duplicates
                is_duplicate = raw_code in code_to_id or raw_name in name_to_id

                if is_duplicate:
                    if merge:
                        # MERGE MODE: Map the CSV ID to the already existing DB ID
                        matched_id = code_to_id.get(raw_code) or name_to_id.get(raw_name)
                        id_translation_map[csv_id] = matched_id
                        continue  # Skip creating a new item
                    else:
                        # RENAME MODE: Append the ID to make it unique
                        if raw_code in code_to_id:
                            raw_code = f"{raw_code}.{csv_id}"
                        if raw_name in name_to_id:
                            raw_name = f"{raw_name}.{csv_id}"

                # 3. Create the Item
                p_source_str = str(row.get('price_source', 'MANUAL')).upper()
                p_source = getattr(PriceSource, p_source_str, PriceSource.MANUAL)

                new_item = Item(**{
                    'code': raw_code,
                    'name': raw_name,
                    'brand': str(row.get('brand', 'Generic')).strip() or 'Generic',
                    'is_category': str(row['is_category']).lower() == 'true',
                    'product_group': str(row.get('product_group', '')).strip() or None,
                    'product_type': str(row.get('product_type', '')).strip() or None,
                    'uom': str(row.get('uom', 'adet')).strip().lower() or 'adet',
                    'dim_x': float(row.get('dim_x', 0.0) or 0.0),
                    'dim_y': float(row.get('dim_y', 0.0) or 0.0),
                    'dim_z': float(row.get('dim_z', 0.0) or 0.0),
                    'base_cost': float(row.get('base_cost', 0.0) or 0.0),
                    'technical_specs': parse_json(row.get('technical_specs')),
                    'price_source': p_source,
                    'reliability_score': int(row.get('reliability_score', 100) or 100)
                })
                
                new_item.item_id = csv_id 
                db.session.add(new_item)
                
                # Update cache for the remainder of the loop
                code_to_id[raw_code] = csv_id
                name_to_id[raw_name] = csv_id
                id_translation_map[csv_id] = csv_id

            # Flush to validate item constraints without permanently committing yet
            db.session.flush()
            click.echo("✅ Items staged successfully. Moving to Compositions...")

            # IMPORT COMPOSITIONS
            click.echo(f"🔗 Scanning {len(df_comps)} BoM relationships...")
            
            for _, row in df_comps.iterrows():
                # 👇 CRITICAL: Re-route IDs through the Translation Map
                p_id = id_translation_map.get(int(row['parent_id']))
                c_id = id_translation_map.get(int(row['child_id']))

                # Failsafe if an item was excluded entirely
                if not p_id or not c_id:
                    continue

                qty = float(row.get('quantity', 1.0) or 1.0)
                s_order = int(row.get('sort_order', 0) or 0)
                opt_attrs = parse_json(row.get('optional_attributes'))

                existing_link = db.session.scalar(db.select(ItemComposition).filter_by(parent_id=p_id, child_id=c_id))
                if existing_link:
                    continue

                parent_obj = db.session.get(Item, p_id)
                child_obj = db.session.get(Item, c_id)

                if parent_obj and child_obj:
                    new_link = ItemComposition(**{
                        'parent_item': parent_obj,
                        'child_item': child_obj,
                        'quantity': qty,
                        'sort_order': s_order,
                        'optional_attributes': opt_attrs
                    })
                    db.session.add(new_link)
            
            # ATOMIC COMMIT: Everything succeeds, or nothing does.
            db.session.commit()
            click.echo("🎉 Atomic Import complete! All data successfully committed.")
            
        except IntegrityError as e:
            db.session.rollback()
            click.echo(f"❌ Database Integrity Error during import: {e.orig}")
            click.echo("⚠️ Transaction rolled back. No partial data was saved.")
            
        except Exception as e:
            db.session.rollback()
            click.echo(f"❌ Unexpected Error during import: {str(e)}")
            click.echo("⚠️ Transaction rolled back. No partial data was saved.")

@cli.command('exportdata')
@click.argument('output_dir', default='.', type=click.Path())
def exportdata(output_dir):
    """Fail-safe export of all EMEK hierarchy (Items & Compositions) to CSV"""
    import json

    import pandas as pd

    from crminaec.core.models import db
    from crminaec.platforms.emek.models import Item, ItemComposition
    
    app = create_app()
    with app.app_context():
        os.makedirs(output_dir, exist_ok=True)
        
        click.echo("📦 Exporting Items...")
        items = db.session.scalars(db.select(Item)).all()
        items_data = []
        for i in items:
            items_data.append({
                'item_id': i.item_id,
                'code': i.code,
                'name': i.name,
                'is_category': getattr(i, 'is_category', False),
                'item_type': i.item_type,
                'node_type': i.node_type.name if i.node_type else '',
                'dim_x': i.dim_x,
                'dim_y': i.dim_y,
                'dim_z': i.dim_z,
                'base_cost': float(i.base_cost or 0.0),
                'technical_specs': json.dumps(i.technical_specs) if i.technical_specs else ''
            })
        pd.DataFrame(items_data).to_csv(os.path.join(output_dir, 'items.csv'), index=False)
        
        click.echo("🔗 Exporting Compositions...")
        comps = db.session.scalars(db.select(ItemComposition)).all()
        comps_data = []
        for c in comps:
            comps_data.append({
                'parent_id': c.parent_id,
                'child_id': c.child_id,
                'quantity': float(c.quantity or 1.0),
                'sort_order': c.sort_order,
                'optional_attributes': json.dumps(c.optional_attributes) if c.optional_attributes else ''
            })
        pd.DataFrame(comps_data).to_csv(os.path.join(output_dir, 'compositions.csv'), index=False)
        
        click.echo(f"✅ Fail-safe export complete! Files saved to {os.path.abspath(output_dir)}")

from crminaec.cli.report_commands import report

cli.add_command(report)

if __name__ == '__main__':
    cli()

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
