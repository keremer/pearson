"""
CLI commands for report generation.
Fully Integrated with crminaec Data-First Architecture
"""
from pathlib import Path
from typing import List, Optional, cast

import click
from sqlalchemy.orm import Session

from crminaec.core.models import db
from crminaec.core.reporting import (CourseDataBuilder, MultiExporter,
                                     TemplateManager)
from crminaec.platforms.emek.models import Item, ItemComposition


@click.group()
def report():
    """Generate course reports."""
    pass


@report.command()
@click.option('--course-id', '-c', '--cid', required=True, type=int, help='Course ID')
@click.option('--format', '-f', 'formats', multiple=True, 
              default=['pdf'], show_default=True,
              type=click.Choice(['pdf', 'html', 'markdown', 'all']),
              help='Output format(s)')
@click.option('--report-type', '-t', 'report_types', multiple=True,
              default=['syllabus'], show_default=True,
              type=click.Choice(['syllabus', 'lesson_plan', 'overview', 'all']),
              help='Type of report(s) to generate')
@click.option('--output-dir', '-o', default='output', show_default=True,
              help='Output directory')
@click.pass_context
def generate(ctx, course_id: int, formats: List[str], 
            report_types: List[str], output_dir: str):
    """Generate reports for a course."""
    # The 'app' object is injected by run.py
    app = ctx.obj['app'] if ctx.obj and 'app' in ctx.obj else None
    
    # Fallback if someone tries to run this command directly instead of through run.py
    if not app:
        from crminaec import create_app
        app = create_app()

    with app.app_context():
        # Get course using the Universal Item schema
        course = db.session.query(Item).filter_by(item_id=course_id, item_type='course').first()
        if not course:
            click.echo(f"❌ Course with ID {course_id} not found", err=True)
            return
        
        # Updated to use name and code
        click.echo(f"📊 Generating reports for: {course.name} ({course.code})")
        
        # Initialize reporting components
        template_manager = TemplateManager()
        data_builder = CourseDataBuilder(template_manager)
        exporter = MultiExporter(output_dir=output_dir)
        
        # Cast the scoped_session to a standard Session to satisfy Pylance
        course_data = data_builder.build_course_data(course, cast(Session, db.session))
        
        # Handle 'all' options
        if 'all' in formats:
            formats = ['pdf', 'html', 'markdown']
        if 'all' in report_types:
            report_types = ['syllabus', 'lesson_plan', 'overview']
        
        generated_files = []
        
        # Generate reports
        for report_type in report_types:
            click.echo(f"  📝 Generating {report_type}...")
            
            # Render content based on report type
            if report_type == 'syllabus':
                content = template_manager.render_syllabus(course_data)
                base_name = f"{course.code}_syllabus"
                
                # Export report
                files = exporter.export_content(content, base_name, list(formats))
                generated_files.extend(files)
                
            elif report_type == 'overview':
                content = template_manager.render_course_overview(course_data)
                base_name = f"{course.code}_overview"
                
                # Export report
                files = exporter.export_content(content, base_name, list(formats))
                generated_files.extend(files)
                
            elif report_type == 'lesson_plan':
                # Generate individual lesson plans using the sorted course.lessons array
                comps = db.session.query(ItemComposition).filter_by(parent_id=course.item_id).order_by(ItemComposition.sort_order).all()
                lessons = [(c.child_item, c.sort_order) for c in comps if c.child_item.item_type == 'lesson']
                for lesson, order in lessons:
                    lesson_data = data_builder.build_lesson_data(lesson, course)
                    content = template_manager.render_lesson_plan(lesson_data)
                    base_name = f"{course.code}_lesson_{order:02d}"
                    
                    # Export lesson plan
                    files = exporter.export_content(content, base_name, list(formats))
                    generated_files.extend(files)
        
        # Summary
        click.echo(f"\n✅ Generated {len(generated_files)} file(s):")
        for file in generated_files:
            # Safely try to make the path relative for cleaner output, fallback to full path
            try:
                display_path = Path(file).relative_to(Path.cwd())
            except ValueError:
                display_path = file
            click.echo(f"  📄 {display_path}")


@report.command()
@click.option('--list-templates', '-l', is_flag=True, 
              help='List available templates')
@click.option('--template-dir', '-d', help='Template directory path')
@click.pass_context
def templates(ctx, list_templates: bool, template_dir: Optional[str]):
    """Manage report templates."""
    if list_templates:
        tm = TemplateManager(template_dir)
        template_files = list(tm.templates_dir.glob("*.j2"))
        
        if template_files:
            click.echo("📁 Available templates:")
            for template in template_files:
                click.echo(f"  • {template.name}")
        else:
            click.echo("📭 No templates found")
            
    elif template_dir:
        # Initialize with custom template directory
        tm = TemplateManager(template_dir)
        click.echo(f"✅ Template manager initialized with: {tm.templates_dir}")