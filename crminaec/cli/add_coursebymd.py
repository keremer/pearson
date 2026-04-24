#!/usr/bin/env python3
"""
Enhanced Course Injector - Handles all syllabus information
Aligned with crminaec Data-First Architecture
"""

import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

# Import the unified app factory and database models
from crminaec import create_app
from crminaec.core.models import db
from crminaec.platforms.emek.models import Item, ItemComposition, NodeType


class EnhancedCourseInjector:
    def __init__(self):
        # We no longer need DatabaseSetup or custom URLs.
        # We will use the Flask app context.
        self.app = create_app()
    
    def parse_comprehensive_syllabus(self, md_content: str) -> Dict[str, Any]:
        """Parse all aspects of the comprehensive syllabus"""
        # --- AI COPY-PASTE ARTIFACT CLEANUP ---
        # Unescape any non-alphanumeric character (e.g. \#, \**, \|) globally
        md_content = re.sub(r'\\([^\w\s])', r'\1', md_content)
        
        # Normalize line endings to prevent \r from breaking regex anchors
        md_content = md_content.replace('\r', '')
        
        data = {}
        
        # Course info (Highly permissive regex for AI variations)
        data['title'] = self._extract_value(r'#\s*([^\n]+)', md_content, "Default Course – Syllabus")
        
        fallback_code = f"CRS-{uuid.uuid4().hex[:6].upper()}"
        data['course_code'] = self._extract_value(r'\*\*Course Code[\*:]*\s*([^\n]+)', md_content, fallback_code)
        data['level'] = self._extract_value(r'\*\*Level[\*:]*\s*([^\n]+)', md_content, "HND Art & Design")
        data['credits'] = self._extract_value(r'\*\*Credits[\*:]*\s*([^\n]+)', md_content, "TBD")
        data['schedule'] = self._extract_value(r'\*\*Course Schedule[\*:]*\s*([^\n]+)', md_content, "TBD")
        data['total_hours'] = self._extract_value(r'\*\*Total Hours.*?[\*:]*\s*([^\n]+)', md_content, "TBD")
        data['prerequisites'] = self._extract_value(r'\*\*Prerequisite.*?[\*:]*\s*([^\n]+)', md_content, "None")
        data['instructor'] = self._extract_value(r'\*\*Instructor[\*:]*\s*([^\n]+)', md_content, "Dr. Kerem ERCOSKUN")
        data['instructor_contact'] = self._extract_value(r'\*\*Instructor Contact[\*:]*\s*([^\n]+)', md_content, "contact@institution.edu")
        data['language'] = self._extract_value(r'\*\*Language[\*:]*\s*([^\n]+)', md_content, "English")
        data['delivery_mode'] = self._extract_value(r'\*\*Delivery[\*:]*\s*([^\n]+)', md_content, "Blended")
        data['description'] = self._extract_section(r'## Course Description and Objectives', md_content)
        
        # Learning Outcomes
        lo_pattern = r'-\s*\*\*(LO\d+)[\*:]*\s*([^\n]+)'
        data['learning_outcomes'] = [
            {'code': match[0], 'description': match[1].strip()}
            for match in re.findall(lo_pattern, md_content)
        ]
        
        # Weekly Structure
        weekly_pattern = r'\|\s*(?:Week\s*)?(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|'
        data['weeks'] = [
            {
                'week': int(match[0]),
                'topic': match[1].strip(),
                'activity': match[2].strip(),
                'date': match[3].strip(),
                'time': match[4].strip(),
                'assignment': match[5].strip()
            }
            for match in re.findall(weekly_pattern, self._extract_section(r'## Weekly Structure', md_content.replace('and Course Schedule', '')))
        ]
        
        # New Academic Sections
        data['teaching_approach'] = self._extract_section(r'## Course Format and Teaching Approach', md_content)
        data['grading_criteria'] = self._extract_section(r'## Assessment and Grading Criteria', md_content)
        data['course_policies'] = self._extract_section(r'## Course Policies', md_content)
        data['support_resources'] = self._extract_section(r'## Student Support Resources', md_content)

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
    
    def _extract_section(self, header_pattern: str, md_content: str) -> str:
        """Extracts everything between a specific header and the next ## header or end of file."""
        match = re.search(fr'{header_pattern}\s*\n(.*?)(?=\n## |\Z)', md_content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _parse_tools_section(self, md_content: str) -> List[Dict[str, str]]:
        tools = []
        
        hardware_section = re.search(r'Minimum computer specs:[\s\n]*(?:-\s*)?([^\n]+)', md_content)
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
                
                # 1. Create Main Course as an Item
                tech_specs = {
                    'instructor': course_data['instructor'],
                    'contact_email': course_data['instructor_contact'],
                    'level': course_data['level'],
                    'credits': course_data['credits'],
                    'schedule': course_data['schedule'],
                    'total_hours': course_data['total_hours'],
                    'prerequisites': course_data['prerequisites'],
                    'language': course_data['language'],
                    'delivery_mode': course_data['delivery_mode'],                    'description': course_data['description'],
                    'teaching_approach': course_data['teaching_approach'],
                    'grading_criteria': course_data['grading_criteria'],
                    'course_policies': course_data['course_policies'],
                    'support_resources': course_data['support_resources'],
                    'objectives': ", ".join([lo['description'] for lo in course_data['learning_outcomes']]),
                    'learning_outcomes': course_data['learning_outcomes'],
                    'assessment_formats': course_data['assessment_formats'],
                    'tools': course_data['tools']
                }
                
                # Idempotent Upsert: Update if exists to prevent IntegrityError crashes
                course = db.session.query(Item).filter_by(code=course_data['course_code']).first()
                if not course:
                    course = Item(
                        name=course_data['title'],
                        code=course_data['course_code'],
                        item_type='course',
                        node_type=NodeType.ACTIVITY,
                        technical_specs=tech_specs
                    )
                    db.session.add(course)
                else:
                    course.name = course_data['title']
                    course.technical_specs = tech_specs
                    db.session.query(ItemComposition).filter_by(parent_id=course.item_id).delete()
                    
                db.session.flush() 
                print(f"✅ Synced course: {course.name} (ID: {course.item_id})")
                
                # 2. Create Lessons with Outcome Mappings
                for week_data in course_data['weeks']:
                    addressed_outcomes = self.map_learning_outcomes_to_lessons(week_data)
                    lesson_tech_specs = {
                        'duration': self._estimate_duration(week_data['activity']),
                        'activity_type': week_data['activity'],
                        'date': week_data['date'],
                        'time': week_data['time'],
                        'assignment_description': week_data['assignment'],
                        'materials_needed': self._get_lesson_materials(week_data),
                        'content': self._build_lesson_content(week_data),
                        'objectives': ", ".join(addressed_outcomes)
                    }
                    
                    lesson = Item(
                        name=f"Week {week_data['week']}: {week_data['topic']}",
                        code=f"{course.code}-W{week_data['week']}",
                        item_type='lesson',
                        node_type=NodeType.ACTIVITY,
                        technical_specs=lesson_tech_specs
                    )
                            
                    db.session.add(lesson)
                    db.session.flush()
                    
                    comp = ItemComposition(parent_item=course, child_item=lesson, sort_order=week_data['week'], optional_attributes={})
                    db.session.add(comp)
                    print(f"  📝 Created lesson: {lesson.name}")
                
                # Commit all changes
                db.session.commit()
                
                print(f"\n🎉 Successfully injected comprehensive course!")
                print(f"📊 Course: {course.name}")
                print(f"🔗 Code: {course.code}")
                print(f"🎯 Learning Outcomes: {len(course_data['learning_outcomes'])}")
                print(f"📋 Assessment Formats: {len(course_data['assessment_formats'])}")
                print(f"🛠️  Tools: {len(course_data['tools'])}")
                print(f"📚 Lessons: {len(course_data['weeks'])}")
                
            return True
            
        except Exception as e:
            print(f"❌ Error injecting course: {e}")
            return False
            
    def _build_lesson_content(self, week_data: Dict[str, Any]) -> str:
        return f"Week {week_data['week']}: {week_data['topic']}\n\nActivity Type:\n{week_data['activity']}\n\nAssignment:\n{week_data['assignment']}\n\nSchedule:\nDate: {week_data['date']}\nTime: {week_data['time']}"

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