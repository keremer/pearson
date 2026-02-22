# pearson/reports/template_manager.py
"""
Template Manager for Course Materials.
Provides Jinja2 template rendering for course reports.
"""
import os
import jinja2
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from sqlalchemy.orm import Session

# Import Pearson models for type hints
try:
    from pearson.models import Course, Lesson, LearningOutcome, AssessmentFormat, Tool
except ImportError:
    # For standalone testing
    pass


class TemplateManager:
    """Manage Jinja2 templates for course report generation."""
    
    def __init__(self, templates_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize TemplateManager.
        
        Args:
            templates_dir: Directory containing Jinja2 templates
        """
        if templates_dir is None:
            # Look for templates in pearson/templates directory
            current_dir = Path(__file__).parent.parent
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
*Generated automatically by Pearson Course Management System*"""
        
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
*Generated automatically by Pearson Course Management System*"""
        
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
*Generated on {{ generated_date }} by Pearson Course Management System*"""
        
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
        return f"""# {course_data.get('course_title', 'Untitled Course')}

**Course Code:** {course_data.get('course_code', 'TBD')}
**Instructor:** {course_data.get('instructor', 'TBD')}

## Description
{course_data.get('course_description', 'No description available.')}

## Lessons
{chr(10).join(f"- {lesson['title']} ({lesson.get('duration', 0)} min)" for lesson in course_data.get('lessons', []))}

*Generated by Pearson Course Management System*"""
    
    def _fallback_lesson_plan(self, lesson_data: Dict[str, Any]) -> str:
        """Fallback lesson plan template if main template fails."""
        return f"""# Lesson {lesson_data.get('order', '?')}: {lesson_data.get('title', 'Untitled Lesson')}

**Duration:** {lesson_data.get('duration', 0)} minutes

## Content
{lesson_data.get('content', 'No content available.')}

*Generated by Pearson Course Management System*"""
    
    def _fallback_course_overview(self, course_data: Dict[str, Any]) -> str:
        """Fallback course overview template if main template fails."""
        return f"""# {course_data.get('course_title', 'Untitled Course')} - Overview

Total Lessons: {len(course_data.get('lessons', []))}
Total Duration: {sum(lesson.get('duration', 0) for lesson in course_data.get('lessons', []))} minutes

*Generated by Pearson Course Management System*"""
    
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
    
    def build_course_data(self, course: 'Course', db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Build course data dictionary for templates.
        
        Args:
            course: Course model instance
            db_session: Optional database session for eager loading
            
        Returns:
            Dictionary with course data for templates
        """
        # Get related data if not already loaded
        lessons = list(course.lessons) if hasattr(course.lessons, '__iter__') else []
        learning_outcomes = list(course.learning_outcomes) if hasattr(course.learning_outcomes, '__iter__') else []
        assessment_formats = list(course.assessment_formats) if hasattr(course.assessment_formats, '__iter__') else []
        tools = list(course.tools) if hasattr(course.tools, '__iter__') else []
        
        # Sort lessons by order
        lessons.sort(key=lambda x: x.order)
        
        # Build course data
        course_data: Dict[str, Any] = {
            'course_title': course.title,
            'course_code': course.course_code,
            'course_description': course.description or 'No description available.',
            'course_aim': course.aim or 'Course aim not specified.',
            'instructor': course.instructor or 'Instructor not specified',
            'contact_email': course.contact_email or 'Contact email not specified',
            'level': course.level or 'N/A',
            'language': course.language or 'English',
            'delivery_mode': course.delivery_mode or 'N/A',
            'objectives': course.objectives or 'No objectives specified.',
            'learning_outcomes': [
                {
                    'id': lo.id,
                    'outcome_text': lo.outcome_text,
                    'created_date': lo.created_date
                }
                for lo in learning_outcomes
            ],
            'assessment_formats': [
                {
                    'id': af.id,
                    'format_type': af.format_type,
                    'percentage': af.percentage,
                    'description': af.description,
                    'created_date': af.created_date
                }
                for af in assessment_formats
            ],
            'tools': [
                {
                    'id': tool.id,
                    'tool_name': tool.tool_name,
                    'purpose': tool.purpose,
                    'license_info': tool.license_info,
                    'created_date': tool.created_date
                }
                for tool in tools
            ],
            'lessons': [
                self._build_lesson_data(lesson)
                for lesson in lessons
            ],
            'created_date': course.created_date,
            'updated_date': course.updated_date,
            'generated_date': datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        return course_data
    
    def build_lesson_data(self, lesson: 'Lesson', 
                         course: Optional['Course'] = None) -> Dict[str, Any]:
        """
        Build lesson data dictionary for templates.
        
        Args:
            lesson: Lesson model instance
            course: Optional Course instance for context
            
        Returns:
            Dictionary with lesson data for templates
        """
        # Get learning outcomes for this lesson
        learning_outcomes = list(lesson.learning_outcomes) if hasattr(lesson.learning_outcomes, '__iter__') else []
        
        lesson_data: Dict[str, Any] = {
            'id': lesson.id,
            'title': lesson.title,
            'order': lesson.order,
            'duration': lesson.duration or 60,
            'content': lesson.content or 'No content available.',
            'activity_type': lesson.activity_type or 'N/A',
            'assignment_description': lesson.assignment_description or 'No assignment specified.',
            'materials_needed': lesson.materials_needed or 'No materials specified.',
            'learning_outcomes': [
                {
                    'id': lo.id,
                    'outcome_text': lo.outcome_text,
                    'created_date': lo.created_date
                }
                for lo in learning_outcomes
            ],
            'created_date': lesson.created_date,
            'course_id': lesson.course_id,
            'course_title': course.title if course else f"Course {lesson.course_id}"
        }
        
        return lesson_data
    
    def _build_lesson_data(self, lesson: 'Lesson') -> Dict[str, Any]:
        """
        Build basic lesson data for course context.
        
        Args:
            lesson: Lesson model instance
            
        Returns:
            Dictionary with lesson data
        """
        return {
            'id': lesson.id,
            'title': lesson.title,
            'order': lesson.order,
            'duration': lesson.duration or 60,
            'content': lesson.content or '',
            'activity_type': lesson.activity_type or 'N/A',
            'assignment_description': lesson.assignment_description or '',
            'materials_needed': lesson.materials_needed or 'N/A',
            'created_date': lesson.created_date
        }