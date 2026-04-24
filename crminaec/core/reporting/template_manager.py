# crminaec/reports/template_manager.py
"""
Template Manager for Course Materials.
Provides Jinja2 template rendering for course reports.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import jinja2
from sqlalchemy.orm import Session

from crminaec.core.models import db
from crminaec.platforms.emek.models import Item, ItemComposition


class TemplateManager:
    """Manage Jinja2 templates for course report generation."""
    
    def __init__(self, templates_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize TemplateManager.
        
        Args:
            templates_dir: Directory containing Jinja2 templates
        """
        if templates_dir is None:
            # Look for templates in crminaec/core/reporting/templates directory
            current_dir = Path(__file__).parent
            self.templates_dir = current_dir / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        print(f"📁 Template directory: {self.templates_dir.absolute()}")
        
        # Create templates directory if it doesn't exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if templates exist, create defaults if not
        if not list(self.templates_dir.glob("*.j2")):
            print("📝 No templates found, creating defaults...")
            self._create_default_templates()
        
        # Setup Jinja2 environment
        try:
            self.env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(self.templates_dir),
                trim_blocks=True,
                lstrip_blocks=True,
                autoescape=True
            )
            print("✅ Jinja2 environment created successfully!")
        except Exception as e:
            print(f"❌ Error creating Jinja2 environment: {e}")
            raise
        
        # Add custom filters
        self._add_custom_filters()
    
    def _create_default_templates(self) -> None:
        """Create default templates if they don't exist."""
        print("📝 Creating default templates...")
        
        # Create syllabus template
        syllabus_template = """# {{ course_title }}

**Course Code:** {{ course_code | default('TBD') }}  
**Instructor:** {{ instructor | default('TBD') }}  
**Contact:** {{ contact_email | default('TBD') }}  
**Level:** {{ level | default('N/A') }}  
**Language:** {{ language | default('English') }}  
**Delivery Mode:** {{ delivery_mode | default('N/A') }}  
**Generated:** {{ generated_date }}

## Course Aim
{{ course_aim }}

## Course Description
{{ course_description }}

## Learning Outcomes
{% for outcome in learning_outcomes %}
- **LO{{ loop.index }}:** {{ outcome.outcome_text }}
{% endfor %}

## Course Outline

| Week | Lesson Title | Duration | Activity Type | Materials Needed |
|------|--------------|----------|---------------|------------------|
{% for lesson in lessons %}
| {{ lesson.order }} | {{ lesson.title }} | {{ lesson.duration }} minutes | {{ lesson.activity_type | default('N/A') }} | {{ lesson.materials_needed | truncate(30) | default('N/A') }} |
{% endfor %}

## Assessment Formats
{% for assessment in assessment_formats %}
- **{{ assessment.format_type }}:** {{ assessment.percentage }}% - {{ assessment.description }}
{% endfor %}

## Tools & Resources
{% for tool in tools %}
- **{{ tool.tool_name }}:** {{ tool.purpose }} ({{ tool.license_info | default('License info not specified') }})
{% endfor %}

---
*Generated automatically by crminaec Course Management System*"""
        
        with open(self.templates_dir / "syllabus.j2", "w", encoding="utf-8") as f:
            f.write(syllabus_template)
        
        # Create lesson plan template
        lesson_template = """# Lesson {{ order }}: {{ title }}

**Course:** {{ course_title }}  
**Week:** {{ order }}  
**Duration:** {{ duration }} minutes  
**Activity Type:** {{ activity_type | default('N/A') }}  
**Date:** {{ date | default('TBD') }}

## Learning Outcomes Addressed
{% for outcome in learning_outcomes %}
- LO{{ loop.index }}: {{ outcome.outcome_text }}
{% endfor %}

## Lesson Content
{{ content }}

## Assignment
{{ assignment_description }}

## Materials Needed
{{ materials_needed }}

---
*Generated automatically by crminaec Course Management System*"""
        
        with open(self.templates_dir / "lesson_plan.j2", "w", encoding="utf-8") as f:
            f.write(lesson_template)
        
        # Create course overview template
        overview_template = """# {{ course_title }} - Course Overview

**Course Code:** {{ course_code }}  
**Instructor:** {{ instructor }}  
**Level:** {{ level }}  
**Total Duration:** {{ total_duration }} minutes  
**Total Lessons:** {{ total_lessons }}

## Quick Stats
- **Average Lesson Duration:** {{ average_duration }} minutes
- **Longest Lesson:** {{ longest_lesson.duration }} minutes ({{ longest_lesson.title }})
- **Shortest Lesson:** {{ shortest_lesson.duration }} minutes ({{ shortest_lesson.title }})

## Learning Outcomes
{% for outcome in learning_outcomes %}
- LO{{ loop.index }}: {{ outcome.outcome_text }}
{% endfor %}

## Lesson Distribution
{% for lesson in lessons %}
### Week {{ lesson.order }}: {{ lesson.title }}
- **Duration:** {{ lesson.duration }} minutes
- **Activity:** {{ lesson.activity_type | default('N/A') }}
- **Materials:** {{ lesson.materials_needed | truncate(80) | default('N/A') }}
{% endfor %}

## Assessment Breakdown
{% for assessment in assessment_formats %}
- {{ assessment.format_type }}: {{ assessment.percentage }}%
{% endfor %}

---
*Generated on {{ generated_date }} by crminaec Course Management System*"""
        
        with open(self.templates_dir / "course_overview.j2", "w", encoding="utf-8") as f:
            f.write(overview_template)
        
        print("✅ Default templates created!")
    
    def _add_custom_filters(self) -> None:
        """Add custom Jinja2 filters."""
        
        def split_filter(value: Optional[str], delimiter: str = ',') -> List[str]:
            """Split string by delimiter."""
            if value and isinstance(value, str):
                return [item.strip() for item in value.split(delimiter)]
            return []
        
        def truncate_filter(value: Optional[str], length: int = 100) -> str:
            """Truncate string to specified length."""
            if value and isinstance(value, str) and len(value) > length:
                return value[:length] + '...'
            return value or ''
        
        def format_duration_filter(minutes: int) -> str:
            """Format duration in minutes to hours and minutes."""
            if not minutes:
                return "0 minutes"
            hours = minutes // 60
            mins = minutes % 60
            if hours == 0:
                return f"{mins} minutes"
            elif mins == 0:
                return f"{hours} hours"
            else:
                return f"{hours}h {mins}m"
        
        # Register filters
        self.env.filters['split'] = split_filter
        self.env.filters['truncate'] = truncate_filter
        self.env.filters['format_duration'] = format_duration_filter
    
    def render_syllabus(self, course_data: Dict[str, Any]) -> str:
        """Render course syllabus template."""
        try:
            template = self.env.get_template("syllabus.j2")
            
            # Ensure all required fields have defaults
            course_data.setdefault('level', 'N/A')
            course_data.setdefault('language', 'English')
            course_data.setdefault('delivery_mode', 'N/A')
            course_data.setdefault('course_aim', 'Course aim not specified.')
            course_data.setdefault('course_description', 'No description available.')
            course_data.setdefault('learning_outcomes', [])
            course_data.setdefault('assessment_formats', [])
            course_data.setdefault('tools', [])
            course_data.setdefault('lessons', [])
            course_data.setdefault('generated_date', datetime.now().strftime("%Y-%m-%d %H:%M"))
            
            return template.render(**course_data)
        except jinja2.TemplateNotFound as e:
            print(f"❌ Syllabus template not found: {e}")
            return self._fallback_syllabus(course_data)
        except Exception as e:
            print(f"❌ Error rendering syllabus: {e}")
            return self._fallback_syllabus(course_data)
    
    def render_lesson_plan(self, lesson_data: Dict[str, Any]) -> str:
        """Render individual lesson plan template."""
        try:
            template = self.env.get_template("lesson_plan.j2")
            
            # Ensure all required fields have defaults
            lesson_data.setdefault('activity_type', 'N/A')
            lesson_data.setdefault('assignment_description', 'No assignment specified.')
            lesson_data.setdefault('materials_needed', 'No materials specified.')
            lesson_data.setdefault('content', 'No content available.')
            lesson_data.setdefault('learning_outcomes', [])
            lesson_data.setdefault('date', datetime.now().strftime("%Y-%m-%d"))
            
            return template.render(**lesson_data)
        except jinja2.TemplateNotFound as e:
            print(f"❌ Lesson plan template not found: {e}")
            return self._fallback_lesson_plan(lesson_data)
        except Exception as e:
            print(f"❌ Error rendering lesson plan: {e}")
            return self._fallback_lesson_plan(lesson_data)
    
    def render_course_overview(self, course_data: Dict[str, Any]) -> str:
        """Render course overview template."""
        try:
            template = self.env.get_template("course_overview.j2")
            
            lessons = course_data.get('lessons', [])
            
            # Calculate statistics
            if lessons:
                durations = [lesson.get('duration', 0) for lesson in lessons]
                total_duration = sum(durations)
                average_duration = total_duration // len(lessons) if len(lessons) > 0 else 0
                
                # Find longest and shortest lessons
                longest_lesson = max(lessons, key=lambda x: x.get('duration', 0))
                shortest_lesson = min(lessons, key=lambda x: x.get('duration', 0))
            else:
                total_duration = 0
                average_duration = 0
                longest_lesson = {'duration': 0, 'title': 'N/A'}
                shortest_lesson = {'duration': 0, 'title': 'N/A'}
            
            # Add calculated data
            course_data.update({
                'total_duration': total_duration,
                'total_lessons': len(lessons),
                'average_duration': average_duration,
                'longest_lesson': longest_lesson,
                'shortest_lesson': shortest_lesson,
                'generated_date': datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            
            return template.render(**course_data)
        except jinja2.TemplateNotFound as e:
            print(f"❌ Course overview template not found: {e}")
            return self._fallback_course_overview(course_data)
        except Exception as e:
            print(f"❌ Error rendering course overview: {e}")
            return self._fallback_course_overview(course_data)
    
    def _fallback_syllabus(self, course_data: Dict[str, Any]) -> str:
        """Fallback syllabus template if main template fails."""
        return f"""# {course_data.get('name', 'Untitled Course')}

**Course Code:** {course_data.get('code', 'TBD')}
**Instructor:** {course_data.get('technical_specs', {}).get('instructor', 'TBD')}

## Description
{course_data.get('technical_specs', {}).get('description', 'No description available.')}

## Lessons
{chr(10).join(f"- {lesson['title']} ({lesson.get('duration', 0)} min)" for lesson in course_data.get('lessons', []))}

*Generated by crminaec Course Management System*"""
    
    def _fallback_lesson_plan(self, lesson_data: Dict[str, Any]) -> str:
        """Fallback lesson plan template if main template fails."""
        return f"""# Lesson {lesson_data.get('order', '?')}: {lesson_data.get('name', 'Untitled Lesson')}

**Duration:** {lesson_data.get('technical_specs', {}).get('duration', 0)} minutes

## Content
{lesson_data.get('technical_specs', {}).get('content', 'No content available.')}

*Generated by crminaec Course Management System*"""
    
    def _fallback_course_overview(self, course_data: Dict[str, Any]) -> str:
        """Fallback course overview template if main template fails."""
        return f"""# {course_data.get('name', 'Untitled Course')} - Overview

Total Lessons: {len(course_data.get('lessons', []))}
Total Duration: {course_data.get('total_duration', 0)} minutes

*Generated by crminaec Course Management System*"""
    
    def save_to_file(self, content: str, filename: str, 
                    output_dir: Union[str, Path] = "output") -> str:
        """
        Save rendered content to file.
        
        Args:
            content: Content to save
            filename: Output filename
            output_dir: Directory to save file
            
        Returns:
            Path to saved file
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        file_path = output_path / filename
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ File saved: {file_path}")
            return str(file_path)
        except Exception as e:
            print(f"❌ Error saving file {filename}: {e}")
            return ""


class CourseDataBuilder:
    """Build course data from database models for template rendering."""
    
    def __init__(self, template_manager: TemplateManager) -> None:
        """
        Initialize CourseDataBuilder.
        
        Args:
            template_manager: TemplateManager instance
        """
        self.template_manager = template_manager
    
    def build_course_data(self, course: Item, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Build course data dictionary for templates.
        """
        if course.item_type != 'course':
            raise ValueError("Provided item is not a course.")

        session = db_session or db.session
        comps = session.query(ItemComposition).filter_by(parent_id=course.item_id).order_by(ItemComposition.sort_order).all()
        lessons = [c.child_item for c in comps if c.child_item and c.child_item.item_type == 'lesson']
        
        total_duration = sum((lesson.technical_specs or {}).get('duration', 60) for lesson in lessons)
        
        # Find longest and shortest lessons
        longest = max(lessons, key=lambda l: (l.technical_specs or {}).get('duration', 60), default=None)
        shortest = min(lessons, key=lambda l: (l.technical_specs or {}).get('duration', 60), default=None)

        specs = course.technical_specs or {}

        return {
            'name': course.name,
            'code': course.code,
            'technical_specs': specs,
            'lessons': lessons,
            'total_lessons': len(lessons),
            'total_duration': total_duration,
            'average_duration': (total_duration // len(lessons)) if lessons else 0,
            'longest_lesson': longest,
            'shortest_lesson': shortest,
            'learning_outcomes': specs.get('learning_outcomes', []),
            'assessment_formats': specs.get('assessment_formats', []),
            'tools': specs.get('tools', []),
            'generated_date': datetime.now().strftime("%Y-%m-%d %H:%M")
        }
     
    def build_lesson_data(self, lesson: Item, course: Optional[Item] = None) -> Dict[str, Any]:
        """
        Build lesson data dictionary for templates.
        """
        if lesson.item_type != 'lesson':
            raise ValueError("Provided item is not a lesson.")
            
        order = 0
        if course:
            comp = db.session.query(ItemComposition).filter_by(child_id=lesson.item_id, parent_id=course.item_id).first()
            order = comp.sort_order if comp else 0
            
        return {
            'name': lesson.name,
            'code': lesson.code,
            'technical_specs': lesson.technical_specs or {},
            'order': order,
            'course_name': course.name if course else "Unknown Course",
            'objectives': (lesson.technical_specs or {}).get('objectives', '').split(','),
            'date': datetime.now().strftime('%Y-%m-%d')
        }