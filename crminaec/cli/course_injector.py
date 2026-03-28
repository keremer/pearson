#!/usr/bin/env python3
"""
Enhanced Course Injector - Handles all syllabus information
Fully Integrated with crminaec Data-First Architecture
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# Import the unified app factory and database models
from crminaec import create_app
from crminaec.core.models import (AssessmentFormat, Course, LearningOutcome,
                                  Lesson, Tool, db)


class CourseInjector:
    def __init__(self):
        # Use the Flask app context instead of a direct DB URL
        self.app = create_app()
    
    def parse_comprehensive_syllabus(self, md_content: str) -> Dict[str, Any]:
        """Parse standardized syllabus - RELIABLE VERSION"""
        data = {}
        
        # Course info
        data['title'] = self._extract_value(r'# ([^\n]+)', md_content, "Course Title")
        data['course_code'] = self._extract_value(r'\*\*Course Code\*\*:\s*([^\n]+)', md_content, "CODE-001")
        data['level'] = self._extract_value(r'\*\*Level\*\*:\s*([^\n]+)', md_content, "HND Art & Design")
        data['instructor'] = self._extract_value(r'\*\*Instructor\*\*:\s*([^\n]+)', md_content, "Kerem")
        data['language'] = self._extract_value(r'\*\*Language\*\*:\s*([^\n]+)', md_content, "English")
        data['delivery_mode'] = self._extract_value(r'\*\*Delivery\*\*:\s*([^\n]+)', md_content, "Weekly seminars")
        data['aim'] = self._extract_value(r'## Course Aim\s*\n([^\n]+)', md_content, "Course aim not specified")
        
        # Learning Outcomes (standardized)
        lo_pattern = r'- \*\*(LO\d+)\**:\s*([^\n]+)'
        data['learning_outcomes'] = [
            {'code': match[0], 'description': match[1].strip()}
            for match in re.findall(lo_pattern, md_content)
        ]
        
        # Weekly Structure
        data['weeks'] = self._parse_standard_weekly_structure(md_content)
        
        # Assessment Formats
        assessment_section = re.search(r'## Assessment Formats\s*\n((?:- [^\n]+\n?)+)', md_content)
        data['assessment_formats'] = []
        if assessment_section:
            for match in re.findall(r'- ([^\n]+)', assessment_section.group(1)):
                data['assessment_formats'].append({
                    'type': self._classify_assessment_type(match),
                    'requirements': match
                })
        
        # Tools
        data['tools'] = self._parse_standard_tools_section(md_content)
        
        return data

    def _parse_standard_weekly_structure(self, md_content: str) -> List[Dict[str, Any]]:
        weeks = []
        weekly_section = re.search(r'## Weekly Structure\s*(.*?)(?=##|\Z)', md_content, re.DOTALL)
        if not weekly_section:
            weekly_section = re.search(r'## Weekly Breakdown\s*(.*?)(?=##|\Z)', md_content, re.DOTALL)
            if not weekly_section:
                return weeks
        
        table_pattern = r'\| (\d+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|'
        matches = re.findall(table_pattern, weekly_section.group(1))
        
        for week_num, topic, activity, assignment in matches:
            weeks.append({
                'week': int(week_num),
                'topic': topic.strip(),
                'activity': activity.strip(),
                'assignment': assignment.strip()
            })
        
        if not weeks:
            table_pattern_3col = r'\| (\d+) \| ([^|]+) \| ([^|]+) \|'
            matches = re.findall(table_pattern_3col, weekly_section.group(1))
            for week_num, topic, focus in matches:
                weeks.append({
                    'week': int(week_num),
                    'topic': topic.strip(),
                    'activity': 'Lecture',
                    'assignment': focus.strip()
                })
        
        return weeks

    def _parse_standard_tools_section(self, md_content: str) -> List[Dict[str, str]]:
        tools = []
        tools_section = re.search(r'## Required Tools & Software\s*(.*?)(?=##|\Z)', md_content, re.DOTALL | re.IGNORECASE)
        if not tools_section:
            print("❌ Could not find Tools & Software section")
            return tools
            
        section_content = tools_section.group(1)
        print(f"🔍 Tools section content length: {len(section_content)}")
        
        hardware_section = re.search(r'Minimum computer specs:\s*((?:\s+- [^\n]+\n?)+)', section_content)
        if hardware_section:
            tools.append({
                'category': 'Hardware', 'name': 'Computer System',
                'specifications': hardware_section.group(1).strip(),
                'description': 'Minimum computer specifications for the course'
            })
            print("  💻 Added hardware tool")
        
        software_section = re.search(r'Software:\s*([^\n]+)', section_content)
        if software_section:
            software_list = [s.strip() for s in software_section.group(1).split(',')]
            for software in software_list:
                if software:
                    tools.append({
                        'category': 'Software', 'name': software, 'specifications': '',
                        'description': f'Required software: {software}'
                    })
                    print(f"  🖥️  Added software: {software}")
        
        ai_section = re.search(r'AI tools:\s*([^\n]+)', section_content)
        if ai_section:
            ai_list = [s.strip() for s in ai_section.group(1).split(',')]
            for ai_tool in ai_list:
                if ai_tool:
                    tools.append({
                        'category': 'AI Tools', 'name': ai_tool, 'specifications': '',
                        'description': f'AI tool: {ai_tool}'
                    })
                    print(f"  🤖 Added AI tool: {ai_tool}")
        
        print(f"✅ Total tools parsed: {len(tools)}")
        return tools

    def _classify_assessment_type(self, content: str) -> str:
        content_lower = content.lower()
        if any(word in content_lower for word in ['written', 'essay', 'report']): return 'Written Assignment'
        elif any(word in content_lower for word in ['presentation', 'slide', 'demo']): return 'Presentation'
        elif any(word in content_lower for word in ['portfolio', 'collection', 'showcase']): return 'Portfolio'
        elif any(word in content_lower for word in ['reflective', 'journal', 'diary']): return 'Reflective Writing'
        return 'Assignment'
    
    def _extract_value(self, pattern: str, content: str, default: str) -> str:
        match = re.search(pattern, content)
        return match.group(1).strip() if match else default
    
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
        """Inject complete course with all relationships"""
        try:
            with open(md_file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            print("📖 Parsing comprehensive syllabus...")
            course_data = self.parse_comprehensive_syllabus(md_content)
            
            print(f"\n📊 PARSING SUMMARY:")
            print(f"  📚 Lessons found: {len(course_data['weeks'])}")
            print(f"  🛠️  Tools found: {len(course_data['tools'])}")
            print(f"  🎯 Learning outcomes: {len(course_data['learning_outcomes'])}")
            print(f"  📋 Assessment formats: {len(course_data['assessment_formats'])}")
            
            # Application Context wrapping for database access
            with self.app.app_context():
                
                # 1. Create Main Course
                course = Course(
                    course_title=course_data['title'],
                    course_code=course_data['course_code'],
                    instructor=course_data['instructor'],
                    contact_email="kerem@institution.edu",
                    level=course_data['level'],
                    language=course_data['language'],
                    delivery_mode=course_data['delivery_mode'],
                    aim=course_data['aim'],
                    description=self._build_comprehensive_description(course_data),
                    objectives=", ".join([lo['description'] for lo in course_data['learning_outcomes']])
                )
                db.session.add(course)
                db.session.flush()
                print(f"\n✅ Created course: {course.course_title} (ID: {course.course_id})")
                
                # 2. Create Learning Outcomes
                learning_outcomes = {}
                for lo_data in course_data['learning_outcomes']:
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
                    # Merge category and specs into the unified purpose field
                    tool_purpose = f"[{tool_data['category']}] {tool_data['description']}"
                    if tool_data.get('specifications'):
                        tool_purpose += f" (Specs: {tool_data['specifications']})"
                        
                    tool = Tool(
                        course_id=course.course_id,
                        tool_name=tool_data['name'],
                        purpose=tool_purpose
                    )
                    db.session.add(tool)
                    print(f"  🛠️  Created tool: {tool.tool_name} ({tool_data['category']})")
                
                # 5. Create Lessons with learning outcome mappings
                lesson_count = 0
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
                    
                    # Map relationships seamlessly using the association table
                    addressed_outcomes = self.map_learning_outcomes_to_lessons(week_data)
                    for lo_code in addressed_outcomes:
                        if lo_code in learning_outcomes:
                            lesson.learning_outcomes.append(learning_outcomes[lo_code])
                            
                    db.session.add(lesson)
                    lesson_count += 1
                    print(f"  📝 Created lesson: {lesson.lesson_title}")
                
                db.session.commit()
                print(f"\n🎉 Successfully injected comprehensive course!")
                print(f"📊 Course: {course.course_title}")
                print(f"🔗 Code: {course.course_code}")
                print(f"🎯 Learning Outcomes: {len(learning_outcomes)}")
                print(f"📋 Assessment Formats: {len(course_data['assessment_formats'])}")
                print(f"🛠️  Tools: {len(course_data['tools'])}")
                print(f"📚 Lessons: {lesson_count}")
                
            return True
            
        except Exception as e:
            print(f"❌ Error injecting course: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def _build_comprehensive_description(self, course_data: Dict[str, Any]) -> str:
        parts = [
            f"Level: {course_data['level']}", f"Language: {course_data['language']}",
            f"Delivery: {course_data['delivery_mode']}", "", f"Aim: {course_data['aim']}", "",
            "Learning Outcomes:", *[f"- {lo['code']}: {lo['description']}" for lo in course_data['learning_outcomes']],
            "", "Assessment Formats:", *[f"- {af['requirements']}" for af in course_data['assessment_formats']]
        ]
        return '\n'.join(parts)
    
    def _build_lesson_content(self, week_data: Dict[str, Any], course_data: Dict[str, Any]) -> str:
        return f"""Week {week_data['week']}: {week_data['topic']}

Activity Type:
{week_data['activity']}

Assignment:
{week_data['assignment']}

Learning Context:
This session focuses on {week_data['topic'].lower()} through {week_data['activity'].lower()}. 
Students will complete: {week_data['assignment']}

Connected to course learning outcomes in professional development."""

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


def main():
    md_file_path = "professional_development_syllabus.md"
    if not Path(md_file_path).exists():
        print("Please create your markdown syllabus file first")
        return
    
    injector = CourseInjector()
    success = injector.inject_comprehensive_course(md_file_path)
    
    if success:
        print("\n🚀 Course injection completed!")
        print("\nNext steps:")
        print("1. Verify: python run.py list_items courses")
        print("2. Generate: python run.py generate --course-id 1 --format all")
    else:
        print("\n❌ Injection failed")


if __name__ == "__main__":
    main()