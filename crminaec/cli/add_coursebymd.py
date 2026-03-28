#!/usr/bin/env python3
"""
Enhanced Course Injector - Handles all syllabus information
Aligned with crminaec Data-First Architecture
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# Import the unified app factory and database models
from crminaec import create_app
from crminaec.core.models import (AssessmentFormat, Course, LearningOutcome,
                                  Lesson, Tool, db)


class EnhancedCourseInjector:
    def __init__(self):
        # We no longer need DatabaseSetup or custom URLs.
        # We will use the Flask app context.
        self.app = create_app()
    
    def parse_comprehensive_syllabus(self, md_content: str) -> Dict[str, Any]:
        """Parse all aspects of the comprehensive syllabus"""
        data = {}
        
        # Basic course information
        data['title'] = self._extract_value(r'# ([^\n]+)', md_content, "Default Course – Syllabus")
        data['course_code'] = self._extract_value(r'\*\*Course Code\*\*:\s*([^\n]+)', md_content, "DC-01")
        data['level'] = self._extract_value(r'\*\*Level\*\*:\s*([^\n]+)', md_content, "HND Art & Design")
        data['instructor'] = self._extract_value(r'\*\*Instructor\*\*:\s*([^\n]+)', md_content, "Dr. Kerem ERCOSKUN")
        data['language'] = self._extract_value(r'\*\*Language\*\*:\s*([^\n]+)', md_content, "English")
        data['delivery_mode'] = self._extract_value(r'\*\*Delivery\*\*:\s*([^\n]+)', md_content, "Weekly seminars, workshops, portfolio sessions")
        data['aim'] = self._extract_value(r'## Course Aim\s*\n([^\n]+)', md_content, "Covent Garden College's courses aims to equip students with the essential skills and knowledge required to navigate and excel in the creative industries.")
        
        # Learning Outcomes
        lo_pattern = r'- \*\*(LO\d+)\**:\s*([^\n]+)'
        data['learning_outcomes'] = [
            {'code': match[0], 'description': match[1].strip()}
            for match in re.findall(lo_pattern, md_content)
        ]
        
        # Weekly Structure
        weekly_pattern = r'\| (\d+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|'
        data['weeks'] = [
            {
                'week': int(match[0]),
                'topic': match[1].strip(),
                'activity': match[2].strip(),
                'assignment': match[3].strip()
            }
            for match in re.findall(weekly_pattern, md_content)
        ]
        
        # Assessment Formats
        assessment_pattern = r'- ([^\n]+)'
        assessment_section = re.search(r'## Assessment Formats\s*\n((?:- [^\n]+\n?)+)', md_content)
        data['assessment_formats'] = []
        if assessment_section:
            for match in re.findall(assessment_pattern, assessment_section.group(1)):
                data['assessment_formats'].append({
                    'type': 'Written Assignment' if 'written' in match.lower() else 
                           'Presentation' if 'presentation' in match.lower() else
                           'Portfolio' if 'portfolio' in match.lower() else
                           'Reflective Writing',
                    'requirements': match
                })
        
        # Tools & Software
        data['tools'] = self._parse_tools_section(md_content)
        
        return data
    
    def _extract_value(self, pattern: str, content: str, default: str) -> str:
        match = re.search(pattern, content)
        return match.group(1).strip() if match else default
    
    def _parse_tools_section(self, md_content: str) -> List[Dict[str, str]]:
        tools = []
        
        hardware_section = re.search(r'Minimum computer specs:\s*((?:\s+- [^\n]+\n?)+)', md_content)
        if hardware_section:
            tools.append({
                'category': 'Hardware',
                'name': 'Computer System',
                'specifications': hardware_section.group(1).strip(),
                'description': 'Minimum computer specifications for the course'
            })
        
        software_section = re.search(r'Software:\s*([^\n]+)', md_content)
        if software_section:
            software_list = [s.strip() for s in software_section.group(1).split(',')]
            for software in software_list:
                tools.append({
                    'category': 'Software',
                    'name': software,
                    'specifications': '',
                    'description': f'Required software: {software}'
                })
        
        ai_section = re.search(r'AI tools:\s*([^\n]+)', md_content)
        if ai_section:
            ai_list = [s.strip() for s in ai_section.group(1).split(',')]
            for ai_tool in ai_list:
                tools.append({
                    'category': 'AI Tools',
                    'name': ai_tool,
                    'specifications': '',
                    'description': f'AI tool: {ai_tool}'
                })
        
        return tools
    
    def map_learning_outcomes_to_lessons(self, week_data: Dict[str, Any]) -> List[str]:
        topic_lower = week_data['topic'].lower()
        
        outcome_mapping = {
            'professional identity': ['LO1'], 'sector mapping': ['LO2'],
            'studio setup': ['LO0'], 'digital setup': ['LO0'],
            'swot': ['LO1'], 'cv': ['LO3'], 'portfolio': ['LO3'],
            'networking': ['LO4'], 'communication': ['LO4'],
            'interview': ['LO4'], 'freelance': ['LO2'],
            'corporate': ['LO2'], 'career': ['LO1', 'LO2'],
            'final project': ['LO1', 'LO2', 'LO3', 'LO4']
        }
        
        addressed_outcomes = []
        for keyword, outcomes in outcome_mapping.items():
            if keyword in topic_lower:
                addressed_outcomes.extend(outcomes)
        
        return list(set(addressed_outcomes)) if addressed_outcomes else ['LO1']
    
    def inject_comprehensive_course(self, md_file_path: str) -> bool:
        """Inject complete course with all relationships using app context"""
        try:
            with open(md_file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            print("📖 Parsing comprehensive syllabus...")
            course_data = self.parse_comprehensive_syllabus(md_content)
            
            # Wrap database operations in the Flask app context
            with self.app.app_context():
                
                # 1. Create Main Course (Using new Dataclass fields)
                course = Course(
                    course_title=course_data['title'],
                    course_code=course_data['course_code'],
                    instructor=course_data['instructor'],
                    contact_email="keremercoskun@coventgarden.college",
                    level=course_data['level'],
                    language=course_data['language'],
                    delivery_mode=course_data['delivery_mode'],
                    aim=course_data['aim'],
                    description=self._build_comprehensive_description(course_data)
                )
                
                db.session.add(course)
                db.session.flush() # Generate the course_id
                print(f"✅ Created course: {course.course_title} (ID: {course.course_id})")
                
                # 2. Create Learning Outcomes
                learning_outcomes = {}
                for lo_data in course_data['learning_outcomes']:
                    # Note: We append the code to the description since our unified model
                    # combined them into a single 'outcome_text' field
                    lo = LearningOutcome(
                        course_id=course.course_id,
                        outcome_text=f"{lo_data['code']}: {lo_data['description']}"
                    )
                    db.session.add(lo)
                    db.session.flush()
                    learning_outcomes[lo_data['code']] = lo
                    print(f"  🎯 Created learning outcome: {lo_data['code']}")
                
                # 3. Create Assessment Formats
                for assessment_data in course_data['assessment_formats']:
                    assessment = AssessmentFormat(
                        course_id=course.course_id,
                        format_type=assessment_data['type'],
                        description=assessment_data['requirements']
                    )
                    db.session.add(assessment)
                    print(f"  📋 Created assessment format: {assessment.format_type}")
                
                # 4. Create Tools
                for tool_data in course_data['tools']:
                    tool = Tool(
                        course_id=course.course_id,
                        tool_name=tool_data['name'],
                        purpose=tool_data['description']
                    )
                    db.session.add(tool)
                    print(f"  🛠️  Created tool: {tool.tool_name}")
                
                # 5. Create Lessons with Outcome Mappings
                for week_data in course_data['weeks']:
                    lesson = Lesson(
                        course_id=course.course_id,
                        lesson_title=f"Week {week_data['week']}: {week_data['topic']}",
                        content=self._build_lesson_content(week_data, course_data),
                        duration=self._estimate_duration(week_data['activity']),
                        order=week_data['week'],
                        activity_type=week_data['activity'],
                        assignment_description=week_data['assignment'],
                        materials_needed=self._get_lesson_materials(week_data)
                    )
                    
                    # Link learning outcomes (Many-to-Many via the association table)
                    addressed_outcomes = self.map_learning_outcomes_to_lessons(week_data)
                    for lo_code in addressed_outcomes:
                        if lo_code in learning_outcomes:
                            # SQLAlchemy 2.0 appends to the relationship list directly
                            lesson.learning_outcomes.append(learning_outcomes[lo_code])
                            
                    db.session.add(lesson)
                    print(f"  📝 Created lesson: {lesson.lesson_title}")
                
                # Commit all changes
                db.session.commit()
                
                print(f"\n🎉 Successfully injected comprehensive course!")
                print(f"📊 Course: {course.course_title}")
                print(f"🔗 Code: {course.course_code}")
                print(f"🎯 Learning Outcomes: {len(learning_outcomes)}")
                print(f"📋 Assessment Formats: {len(course_data['assessment_formats'])}")
                print(f"🛠️  Tools: {len(course_data['tools'])}")
                print(f"📚 Lessons: {len(course_data['weeks'])}")
                
            return True
            
        except Exception as e:
            print(f"❌ Error injecting course: {e}")
            return False
            
    def _build_comprehensive_description(self, course_data: Dict[str, Any]) -> str:
        parts = [
            f"Level: {course_data['level']}", f"Language: {course_data['language']}",
            f"Delivery: {course_data['delivery_mode']}", "",
            f"Aim: {course_data['aim']}", "",
            "Learning Outcomes:",
            *[f"- {lo['code']}: {lo['description']}" for lo in course_data['learning_outcomes']],
            "", "Assessment Formats:",
            *[f"- {af['requirements']}" for af in course_data['assessment_formats']]
        ]
        return '\n'.join(parts)
    
    def _build_lesson_content(self, week_data: Dict[str, Any], course_data: Dict[str, Any]) -> str:
        return f"""Week {week_data['week']}: {week_data['topic']}\n\nActivity Type:\n{week_data['activity']}\n\nAssignment:\n{week_data['assignment']}\n\nLearning Context:\nThis session focuses on {week_data['topic'].lower()} through {week_data['activity'].lower()}.\nStudents will complete: {week_data['assignment']}\n\nConnected to course learning outcomes in professional development."""

    def _estimate_duration(self, activity: str) -> int:
        activity_lower = activity.lower()
        if any(x in activity_lower for x in ['workshop', 'demo', 'simulation', 'role play']): return 120
        elif any(x in activity_lower for x in ['presentation', 'discussion', 'analysis']): return 90
        return 60
    
    def _get_lesson_materials(self, week_data: Dict[str, Any]) -> str:
        base = ["Computer", "Note-taking materials"]
        activity = week_data['activity'].lower()
        if 'presentation' in activity: base.extend(["Presentation software", "Research resources"])
        elif 'workshop' in activity: base.extend(["Workshop templates", "Examples"])
        elif 'demo' in activity: base.extend(["Demo software", "Tutorial guides"])
        return ', '.join(base)

# We can keep this for direct testing, but normally it's called via run.py
def main():
    md_file_path = "professional_development_syllabus.md"
    if not Path(md_file_path).exists():
        print("Please create your markdown syllabus file first")
        return
    
    injector = EnhancedCourseInjector()
    if injector.inject_comprehensive_course(md_file_path):
        print("\n🚀 Course injection completed!")
        print("\nNext steps:")
        print("1. Verify: python run.py list_items courses")
        print("2. Generate: python run.py generate --course-id 1 --format all")
    else:
        print("\n❌ Injection failed")

if __name__ == "__main__":
    main()