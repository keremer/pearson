# pearson/cli/report_commands.py
"""
CLI commands for report generation.
"""
import click
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

from ..models import Course
from ..reports import TemplateManager, CourseDataBuilder, MultiExporter


@click.group()
def report():
    """Generate course reports."""
    pass


@report.command()
@click.option('--course-id', required=True, type=int, help='Course ID')
@click.option('--format', '-f', 'formats', multiple=True, 
              default=['pdf'], show_default=True,
              type=click.Choice(['pdf', 'html', 'markdown', 'all']),
              help='Output format(s)')
@click.option('--report-type', '-t', 'report_types', multiple=True,
              default=['syllabus'], show_default=True,
              type=click.Choice(['syllabus', 'lesson_plan', 'overview', 'all']),
              help='Type of report(s) to generate')
@click.option('--output-dir', '-o', default='reports', show_default=True,
              help='Output directory')
@click.pass_context
def generate(ctx, course_id: int, formats: List[str], 
            report_types: List[str], output_dir: str):
    """Generate reports for a course."""
    app = ctx.obj['app']
    
    with app.app_context():
        db_session: Session = app.extensions['sqlalchemy'].db.session
        
        # Get course
        course = db_session.get(Course, course_id)
        if not course:
            click.echo(f"❌ Course with ID {course_id} not found", err=True)
            return
        
        click.echo(f"📊 Generating reports for: {course.title} ({course.course_code})")
        
        # Initialize reporting components
        template_manager = TemplateManager()
        data_builder = CourseDataBuilder(template_manager)
        exporter = MultiExporter(output_dir=output_dir)
        
        # Build course data
        course_data = data_builder.build_course_data(course, db_session)
        
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
                base_name = f"{course.course_code}_syllabus"
                
                # Export report
                files = exporter.export_content(content, base_name, list(formats))
                generated_files.extend(files)
            elif report_type == 'overview':
                content = template_manager.render_course_overview(course_data)
                base_name = f"{course.course_code}_overview"
                
                # Export report
                files = exporter.export_content(content, base_name, list(formats))
                generated_files.extend(files)
            elif report_type == 'lesson_plan':
                # Generate individual lesson plans
                for lesson in course.lessons:
                    lesson_data = data_builder.build_lesson_data(lesson, course)
                    content = template_manager.render_lesson_plan(lesson_data)
                    base_name = f"{course.course_code}_lesson_{lesson.order:02d}"
                    
                    # Export lesson plan
                    files = exporter.export_content(content, base_name, list(formats))
                    generated_files.extend(files)
        
        # Summary
        click.echo(f"\n✅ Generated {len(generated_files)} file(s):")
        for file in generated_files:
            click.echo(f"  📄 {Path(file).relative_to('.')}")


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