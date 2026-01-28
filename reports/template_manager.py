#!/usr/bin/env python3
"""
Template Manager for Course Materials - FIXED FOR NEW STRUCTURE
Updated for shared models and correct template paths
"""

import os
import jinja2  # Fixed typo: was 'jlnja2'
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

class TemplateManager:
    def __init__(self, templates_dir: Optional[str] = None):  # Fixed: Use Optional
        # Fix template path for new structure
        if templates_dir is None:
            # Look for templates in project root templates/ directory
            current_dir = Path(__file__).parent.parent
            self.templates_dir = current_dir / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        print(f"📁 Looking for templates in: {self.templates_dir.absolute()}")
        
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
    
    def _create_default_templates(self):
        """Create default templates if they don't exist"""
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
- **{{ outcome.code }}:** {{ outcome.description }}
{% endfor %}

## Course Outline

| Week | Lesson Title | Duration | Activity Type | Assignment |
|------|--------------|----------|---------------|------------|
{% for lesson in lessons %}
| {{ lesson.order }} | {{ lesson.title }} | {{ lesson.duration }} minutes | {{ lesson.activity_type | default('N/A') }} | {{ lesson.assignment_description | truncate(50) }} |
{% endfor %}

## Assessment Formats
{% for assessment in assessment_formats %}
- **{{ assessment.format_type }}:** {{ assessment.requirements }}
{% endfor %}

## Tools & Resources
{% for tool in tools %}
- **{{ tool.category }} - {{ tool.name }}:** {{ tool.specifications | default(tool.description) }}
{% endfor %}

---
*Generated automatically by Course Automation System*"""
        
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
- {{ outcome.code }}: {{ outcome.description }}
{% endfor %}

## Lesson Content
{{ content }}

## Assignment
{{ assignment_description }}

## Materials Needed
{{ materials_needed }}

## Activities
**Primary Activity:** {{ activity_type }}

---
*Generated automatically by Course Automation System*"""
        
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
- {{ outcome.code }}: {{ outcome.description }}
{% endfor %}

## Lesson Distribution
{% for lesson in lessons %}
### Week {{ lesson.order }}: {{ lesson.title }}
- **Duration:** {{ lesson.duration }} minutes
- **Activity:** {{ lesson.activity_type | default('N/A') }}
- **Assignment:** {{ lesson.assignment_description | truncate(80) }}
{% endfor %}

---
*Generated on {{ generated_date }}*"""
        
        with open(self.templates_dir / "course_overview.j2", "w", encoding="utf-8") as f:
            f.write(overview_template)
        
        print("✅ Default templates created!")
    
    def _add_custom_filters(self):
        """Add custom Jinja2 filters"""
        
        def split_filter(value, delimiter=','):
            """Split string by delimiter"""
            if value and isinstance(value, str):
                return [item.strip() for item in value.split(delimiter)]
            return []
        
        def truncate_filter(value, length=100):
            """Truncate string to specified length"""
            if value and isinstance(value, str) and len(value) > length:
                return value[:length] + '...'
            return value or ''
        
        # Register filters
        self.env.filters['split'] = split_filter
        self.env.filters['truncate'] = truncate_filter
    
    def render_syllabus(self, course_data: Dict[str, Any]) -> str:
        """Render course syllabus template"""
        try:
            template = self.env.get_template("syllabus.j2")
            
            # Ensure all required fields have defaults
            course_data.setdefault('level', 'N/A')
            course_data.setdefault('language', 'English')
            course_data.setdefault('delivery_mode', 'N/A')
            course_data.setdefault('course_aim', 'N/A')
            course_data.setdefault('learning_outcomes', [])
            course_data.setdefault('assessment_formats', [])
            course_data.setdefault('tools', [])
            course_data.setdefault('generated_date', datetime.now().strftime("%Y-%m-%d %H:%M"))
            
            return template.render(**course_data)
        except jinja2.TemplateNotFound:
            print("❌ Syllabus template not found! Using fallback.")
            return self._fallback_syllabus(course_data)
        except Exception as e:
            print(f"❌ Error rendering syllabus: {e}")
            return self._fallback_syllabus(course_data)
    
    def render_lesson_plan(self, lesson_data: Dict[str, Any]) -> str:
        """Render individual lesson plan template"""
        try:
            template = self.env.get_template("lesson_plan.j2")
            
            # Ensure all required fields have defaults
            lesson_data.setdefault('activity_type', 'N/A')
            lesson_data.setdefault('assignment_description', 'N/A')
            lesson_data.setdefault('materials_needed', 'N/A')
            lesson_data.setdefault('learning_outcomes', [])
            lesson_data.setdefault('date', 'TBD')
            
            return template.render(**lesson_data)
        except jinja2.TemplateNotFound:
            print("❌ Lesson plan template not found! Using fallback.")
            return self._fallback_lesson_plan(lesson_data)
        except Exception as e:
            print(f"❌ Error rendering lesson plan: {e}")
            return self._fallback_lesson_plan(lesson_data)
    
    def render_course_overview(self, course_data: Dict[str, Any]) -> str:
        """Render course overview template"""
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
        except jinja2.TemplateNotFound:
            print("❌ Course overview template not found! Using fallback.")
            return self._fallback_course_overview(course_data)
        except Exception as e:
            print(f"❌ Error rendering course overview: {e}")
            return self._fallback_course_overview(course_data)
    
    def _fallback_syllabus(self, course_data: Dict[str, Any]) -> str:
        """Fallback syllabus template if main template fails"""
        return f"""# {course_data.get('course_title', 'Untitled Course')}

**Course Code:** {course_data.get('course_code', 'TBD')}
**Instructor:** {course_data.get('instructor', 'TBD')}

## Description
{course_data.get('course_description', 'No description available.')}

## Lessons
{chr(10).join(f"- {lesson['title']} ({lesson.get('duration', 0)} min)" for lesson in course_data.get('lessons', []))}
"""
    
    def _fallback_lesson_plan(self, lesson_data: Dict[str, Any]) -> str:
        """Fallback lesson plan template if main template fails"""
        return f"""# Lesson {lesson_data.get('order', '?')}: {lesson_data.get('title', 'Untitled Lesson')}

**Duration:** {lesson_data.get('duration', 0)} minutes

## Content
{lesson_data.get('content', 'No content available.')}
"""
    
    def _fallback_course_overview(self, course_data: Dict[str, Any]) -> str:
        """Fallback course overview template if main template fails"""
        return f"""# {course_data.get('course_title', 'Untitled Course')} - Overview

Total Lessons: {len(course_data.get('lessons', []))}
Total Duration: {sum(lesson.get('duration', 0) for lesson in course_data.get('lessons', []))} minutes
"""
    
    def save_to_file(self, content: str, filename: str, output_dir: str = "output") -> str:
        """Save rendered content to file"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        file_path = output_path / filename
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return str(file_path)
        except Exception as e:
            print(f"❌ Error saving file {filename}: {e}")
            return ""

class CourseDataBuilder:
    """Helper class to build course data from database models"""
    
    def __init__(self, template_manager: TemplateManager):
        self.template_manager = template_manager
    
    def build_course_data(self, course, lessons) -> Dict[str, Any]:
        """Build course data dictionary for templates - FIXED for shared models"""
        # Handle objectives safely - they're stored as comma-separated strings
        objectives = []
        if hasattr(course, 'objectives') and course.objectives:
            if isinstance(course.objectives, str):
                objectives = [obj.strip() for obj in course.objectives.split(',')]
        
        # Build enhanced course data
        course_data = {
            'course_title': course.title,
            'course_code': course.course_code,
            'course_description': course.description or 'No description available.',
            'course_aim': getattr(course, 'aim', 'No aim specified.'),
            'instructor': course.instructor or 'TBD',
            'contact_email': course.contact_email or 'TBD',
            'level': getattr(course, 'level', 'N/A'),
            'language': getattr(course, 'language', 'English'),
            'delivery_mode': getattr(course, 'delivery_mode', 'N/A'),
            'objectives': objectives,  # Use the parsed list
            'learning_outcomes': [],
            'assessment_formats': [],
            'tools': [],
            'lessons': self._build_lessons_data(lessons)
        }
        
        # Add learning outcomes if available
        if hasattr(course, 'learning_outcomes'):
            course_data['learning_outcomes'] = [
                {'code': lo.code, 'description': lo.description}
                for lo in course.learning_outcomes
            ]
        
        return course_data
    
    def build_lesson_data(self, lesson, course) -> Dict[str, Any]:
        """Build lesson data dictionary for templates - FIXED for shared models"""
        # Handle objectives safely
        objectives = []
        if hasattr(lesson, 'objectives') and lesson.objectives:
            if isinstance(lesson.objectives, str):
                objectives = [obj.strip() for obj in lesson.objectives.split(',')]
        
        lesson_data = {
            'title': lesson.title,
            'order': lesson.order,
            'duration': lesson.duration or 0,
            'content': lesson.content or 'No content available.',
            'objectives': objectives,  # Use the parsed list
            'materials_needed': lesson.materials_needed or 'No materials specified.',
            'activity_type': getattr(lesson, 'activity_type', 'N/A'),
            'assignment_description': getattr(lesson, 'assignment_description', 'No assignment specified.'),
            'course_title': course.title,
            'learning_outcomes': []
        }
        
        # Add learning outcomes if available
        if hasattr(lesson, 'learning_outcomes'):
            lesson_data['learning_outcomes'] = [
                {'code': lo.learning_outcome.code, 'description': lo.learning_outcome.description}
                for lo in lesson.learning_outcomes
            ]
        
        return lesson_data
    
    def _build_lessons_data(self, lessons) -> List[Dict[str, Any]]:
        """Build lessons data list - FIXED for shared models"""
        lessons_data = []
        for lesson in lessons:
            # Handle objectives safely
            objectives = []
            if hasattr(lesson, 'objectives') and lesson.objectives:
                if isinstance(lesson.objectives, str):
                    objectives = [obj.strip() for obj in lesson.objectives.split(',')]
            
            lesson_data = {
                'title': lesson.title,
                'order': lesson.order,
                'duration': lesson.duration or 0,
                'content': lesson.content or '',
                'objectives': objectives,  # Use parsed list
                'activity_type': getattr(lesson, 'activity_type', 'N/A'),
                'assignment_description': getattr(lesson, 'assignment_description', '')
            }
            lessons_data.append(lesson_data)
        return lessons_data

def main():
    """Test the template system"""
    print("🎯 Template System Test")
    print("=" * 50)
    
    # Initialize template manager
    template_manager = TemplateManager()
    data_builder = CourseDataBuilder(template_manager)
    
    print("✅ Template system initialized!")
    
    # Test with sample data
    sample_course_data = {
        'course_title': 'Test Course',
        'course_code': 'TEST101',
        'course_description': 'This is a test course description.',
        'instructor': 'Test Instructor',
        'contact_email': 'test@example.com',
        'level': 'HND Art & Design',
        'language': 'English',
        'delivery_mode': 'Weekly seminars',
        'objectives': ['Learn A', 'Understand B', 'Apply C'],
        'learning_outcomes': [
            {'code': 'LO1', 'description': 'Understand professional identity'},
            {'code': 'LO2', 'description': 'Map creative sectors'}
        ],
        'lessons': [
            {
                'title': 'Test Lesson 1', 
                'order': 1, 
                'duration': 60, 
                'content': 'Content for lesson 1',
                'activity_type': 'Workshop',
                'assignment_description': 'Complete SWOT analysis'
            },
            {
                'title': 'Test Lesson 2', 
                'order': 2, 
                'duration': 90, 
                'content': 'Content for lesson 2',
                'activity_type': 'Presentation',
                'assignment_description': 'Prepare portfolio'
            }
        ]
    }
    
    # Test rendering
    print("\n📝 Testing template rendering...")
    syllabus_content = template_manager.render_syllabus(sample_course_data)
    overview_content = template_manager.render_course_overview(sample_course_data)
    
    # Save test files
    syllabus_file = template_manager.save_to_file(syllabus_content, "test_syllabus.md")
    overview_file = template_manager.save_to_file(overview_content, "test_overview.md")
    
    print(f"✅ Sample syllabus saved: {syllabus_file}")
    print(f"✅ Sample overview saved: {overview_file}")
    print("\n🎉 Template system test completed!")

if __name__ == "__main__":
    main()