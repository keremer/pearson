#!/usr/bin/env python3
"""
Enhanced Course Injector - Handles all syllabus information
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add app to path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from cli.setup import DatabaseSetup
from shared import Course, Lesson, LearningOutcome, AssessmentFormat, Tool, LessonLearningOutcome

class EnhancedCourseInjector:
    def __init__(self, database_url='sqlite:///courses.db'):
        self.db_setup = DatabaseSetup(database_url)
    
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
        data['aim'] = self._extract_value(r'## Course Aim\s*\n([^\n]+)', md_content, "Covent Garden College's courses aims to equip students with the essential skills and knowledge required to navigate and excel in the creative industries. Through a combination of theoretical insights and practical applications, students will develop a comprehensive understanding of professional practices, industry standards, and career development strategies.")
        
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
        """Extract value from markdown using regex pattern"""
        match = re.search(pattern, content)
        return match.group(1).strip() if match else default
    
    def _parse_tools_section(self, md_content: str) -> List[Dict[str, str]]:
        """Parse the tools and software section"""
        tools = []
        
        # Hardware specifications
        hardware_section = re.search(r'Minimum computer specs:\s*((?:\s+- [^\n]+\n?)+)', md_content)
        if hardware_section:
            tools.append({
                'category': 'Hardware',
                'name': 'Computer System',
                'specifications': hardware_section.group(1).strip(),
                'description': 'Minimum computer specifications for the course'
            })
        
        # Software tools
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
        
        # AI tools
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
        """Map learning outcomes to each lesson based on topic"""
        topic_lower = week_data['topic'].lower()
        
        outcome_mapping = {
            'professional identity': ['LO1'],
            'sector mapping': ['LO2'],
            'studio setup': ['LO0'],
            'digital setup': ['LO0'],
            'swot': ['LO1'],
            'cv': ['LO3'],
            'portfolio': ['LO3'],
            'networking': ['LO4'],
            'communication': ['LO4'],
            'interview': ['LO4'],
            'freelance': ['LO2'],
            'corporate': ['LO2'],
            'career': ['LO1', 'LO2'],
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
            # Read and parse syllabus
            with open(md_file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            print("📖 Parsing comprehensive syllabus...")
            course_data = self.parse_comprehensive_syllabus(md_content)
            
            session = self.db_setup.Session()
            
            # Create main course
            course = Course(
                title=course_data['title'],
                course_code=course_data['course_code'],
                instructor=course_data['instructor'],
                contact_email="keremercoskun@coventgarden.college",
                level=course_data['level'],
                language=course_data['language'],
                delivery_mode=course_data['delivery_mode'],
                aim=course_data['aim'],
                description=self._build_comprehensive_description(course_data)
            )
            
            session.add(course)
            session.flush()
            print(f"✅ Created course: {course.title} (ID: {course.id})")
            
            # Create learning outcomes
            learning_outcomes = {}
            for lo_data in course_data['learning_outcomes']:
                lo = LearningOutcome(
                    code=lo_data['code'],
                    description=lo_data['description']
                )
                session.add(lo)
                session.flush()
                learning_outcomes[lo_data['code']] = lo
                print(f"  🎯 Created learning outcome: {lo.code}")
            
            # Create assessment formats
            for assessment_data in course_data['assessment_formats']:
                assessment = AssessmentFormat(
                    course_id=course.id,
                    format_type=assessment_data['type'],
                    requirements=assessment_data['requirements'],
                    description=assessment_data['requirements']
                )
                session.add(assessment)
                print(f"  📋 Created assessment format: {assessment.format_type}")
            
            # Create tools
            for tool_data in course_data['tools']:
                tool = Tool(
                    category=tool_data['category'],
                    name=tool_data['name'],
                    specifications=tool_data.get('specifications', ''),
                    description=tool_data['description']
                )
                session.add(tool)
                print(f"  🛠️  Created tool: {tool.name} ({tool.category})")
            
            # Create lessons with learning outcome mappings
            for week_data in course_data['weeks']:
                lesson = Lesson(
                    course_id=course.id,
                    title=f"Week {week_data['week']}: {week_data['topic']}",
                    content=self._build_lesson_content(week_data, course_data),
                    duration=self._estimate_duration(week_data['activity']),
                    order=week_data['week'],
                    activity_type=week_data['activity'],
                    assignment_description=week_data['assignment'],
                    materials_needed=self._get_lesson_materials(week_data)
                )
                session.add(lesson)
                session.flush()
                print(f"  📝 Created lesson: {lesson.title}")
                
                # Link learning outcomes to lesson
                addressed_outcomes = self.map_learning_outcomes_to_lessons(week_data)
                for lo_code in addressed_outcomes:
                    if lo_code in learning_outcomes:
                        lesson_lo =LessonLearningOutcome(
                            lesson_id=lesson.id,
                            learning_outcome_id=learning_outcomes[lo_code].id,
                            strength='Primary'
                        )
                        session.add(lesson_lo)
            
            session.commit()
            print(f"\n🎉 Successfully injected comprehensive course!")
            print(f"📊 Course: {course.title}")
            print(f"🔗 Code: {course.course_code}")
            print(f"🎯 Learning Outcomes: {len(learning_outcomes)}")
            print(f"📋 Assessment Formats: {len(course_data['assessment_formats'])}")
            print(f"🛠️  Tools: {len(course_data['tools'])}")
            print(f"📚 Lessons: {len(course_data['weeks'])}")
            
            session.close()
            return True
            
        except Exception as e:
            print(f"❌ Error injecting course: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _build_comprehensive_description(self, course_data: Dict[str, Any]) -> str:
        """Build detailed course description"""
        parts = [
            f"Level: {course_data['level']}",
            f"Language: {course_data['language']}",
            f"Delivery: {course_data['delivery_mode']}",
            "",
            f"Aim: {course_data['aim']}",
            "",
            "Learning Outcomes:",
            *[f"- {lo['code']}: {lo['description']}" for lo in course_data['learning_outcomes']],
            "",
            "Assessment Formats:",
            *[f"- {af['requirements']}" for af in course_data['assessment_formats']]
        ]
        return '\n'.join(parts)
    
    def _build_lesson_content(self, week_data: Dict[str, Any], course_data: Dict[str, Any]) -> str:
        """Build detailed lesson content"""
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
        """Estimate lesson duration"""
        activity_lower = activity.lower()
        if any(x in activity_lower for x in ['workshop', 'demo', 'simulation', 'role play']):
            return 120
        elif any(x in activity_lower for x in ['presentation', 'discussion', 'analysis']):
            return 90
        else:
            return 60
    
    def _get_lesson_materials(self, week_data: Dict[str, Any]) -> str:
        """Determine materials for each lesson"""
        base = ["Computer", "Note-taking materials"]
        activity = week_data['activity'].lower()
        
        if 'presentation' in activity:
            base.extend(["Presentation software", "Research resources"])
        elif 'workshop' in activity:
            base.extend(["Workshop templates", "Examples"])
        elif 'demo' in activity:
            base.extend(["Demo software", "Tutorial guides"])
        
        return ', '.join(base)

def main():
    """Main injection function"""
    md_file_path = "professional_development_syllabus.md"
    
    # Create file if it doesn't exist
    if not Path(md_file_path).exists():
        print("Please create your markdown syllabus file first")
        return
    
    injector = EnhancedCourseInjector()
    success = injector.inject_comprehensive_course(md_file_path)
    
    if success:
        print("\n🚀 Course injection completed!")
        print("\nNext steps:")
        print("1. Verify: python main.py list courses")
        print("2. Generate: python main.py generate --course-id 3 --format all")
    else:
        print("\n❌ Injection failed")

if __name__ == "__main__":
    main()