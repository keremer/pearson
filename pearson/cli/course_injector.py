#!/usr/bin/env python3
"""
Enhanced Course Injector - Handles all syllabus information
FIXED: Uses association table instead of non-existent LessonLearningOutcome model
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Any

# Fix imports for new structure
from pearson.cli.setup import DatabaseSetup
from pearson.models import Course, Lesson, LearningOutcome, AssessmentFormat, Tool, lesson_learning_outcome


class CourseInjector:
    def __init__(self, database_url='sqlite:///courses.db'):
        self.db_setup = DatabaseSetup(database_url)
    
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
        
        # Weekly Structure (standardized 4-column table)
        data['weeks'] = self._parse_standard_weekly_structure(md_content)
        
        # Assessment Formats (standardized section)
        assessment_section = re.search(r'## Assessment Formats\s*\n((?:- [^\n]+\n?)+)', md_content)
        data['assessment_formats'] = []
        if assessment_section:
            for match in re.findall(r'- ([^\n]+)', assessment_section.group(1)):
                data['assessment_formats'].append({
                    'type': self._classify_assessment_type(match),
                    'requirements': match
                })
        
        # Tools (standardized section)
        data['tools'] = self._parse_standard_tools_section(md_content)
        
        return data

    def _parse_standard_weekly_structure(self, md_content: str) -> List[Dict[str, Any]]:
        """Parse the STANDARDIZED weekly structure table"""
        weeks = []
        
        weekly_section = re.search(r'## Weekly Structure\s*(.*?)(?=##|\Z)', md_content, re.DOTALL)
        if not weekly_section:
            # Try alternative section names
            weekly_section = re.search(r'## Weekly Breakdown\s*(.*?)(?=##|\Z)', md_content, re.DOTALL)
            if not weekly_section:
                return weeks
        
        # Look for standardized 4-column table
        table_pattern = r'\| (\d+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|'
        matches = re.findall(table_pattern, weekly_section.group(1))
        
        for week_num, topic, activity, assignment in matches:
            weeks.append({
                'week': int(week_num),
                'topic': topic.strip(),
                'activity': activity.strip(),
                'assignment': assignment.strip()
            })
        
        # If no matches found with 4 columns, try 3 columns (your current format)
        if not weeks:
            table_pattern_3col = r'\| (\d+) \| ([^|]+) \| ([^|]+) \|'
            matches = re.findall(table_pattern_3col, weekly_section.group(1))
            for week_num, topic, focus in matches:
                weeks.append({
                    'week': int(week_num),
                    'topic': topic.strip(),
                    'activity': 'Lecture',  # Default for 3-column format
                    'assignment': focus.strip()
                })
        
        return weeks

    def _parse_standard_tools_section(self, md_content: str) -> List[Dict[str, str]]:
        """Parse ONLY the tools and software section - STANDARDIZED version"""
        tools = []
        
        # Find the specific "Required Tools & Software" section
        tools_section = re.search(r'## Required Tools & Software\s*(.*?)(?=##|\Z)', md_content, re.DOTALL | re.IGNORECASE)
        if not tools_section:
            print("❌ Could not find Tools & Software section")
            return tools
            
        section_content = tools_section.group(1)
        print(f"🔍 Tools section content length: {len(section_content)}")
        
        # Hardware specifications - count as ONE tool
        hardware_section = re.search(r'Minimum computer specs:\s*((?:\s+- [^\n]+\n?)+)', section_content)
        if hardware_section:
            tools.append({
                'category': 'Hardware',
                'name': 'Computer System',
                'specifications': hardware_section.group(1).strip(),
                'description': 'Minimum computer specifications for the course'
            })
            print("  💻 Added hardware tool")
        
        # Software tools - count individual software
        software_section = re.search(r'Software:\s*([^\n]+)', section_content)
        if software_section:
            software_list = [s.strip() for s in software_section.group(1).split(',')]
            for software in software_list:
                if software:  # Skip empty strings
                    tools.append({
                        'category': 'Software',
                        'name': software,
                        'specifications': '',
                        'description': f'Required software: {software}'
                    })
                    print(f"  🖥️  Added software: {software}")
        
        # AI tools - count individual AI tools
        ai_section = re.search(r'AI tools:\s*([^\n]+)', section_content)
        if ai_section:
            ai_list = [s.strip() for s in ai_section.group(1).split(',')]
            for ai_tool in ai_list:
                if ai_tool:  # Skip empty strings
                    tools.append({
                        'category': 'AI Tools',
                        'name': ai_tool,
                        'specifications': '',
                        'description': f'AI tool: {ai_tool}'
                    })
                    print(f"  🤖 Added AI tool: {ai_tool}")
        
        print(f"✅ Total tools parsed: {len(tools)}")
        return tools

    def _classify_assessment_type(self, content: str) -> str:
        """Classify assessment type based on content"""
        content_lower = content.lower()
        if any(word in content_lower for word in ['written', 'essay', 'report']):
            return 'Written Assignment'
        elif any(word in content_lower for word in ['presentation', 'slide', 'demo']):
            return 'Presentation'
        elif any(word in content_lower for word in ['portfolio', 'collection', 'showcase']):
            return 'Portfolio'
        elif any(word in content_lower for word in ['reflective', 'journal', 'diary']):
            return 'Reflective Writing'
        else:
            return 'Assignment'
    
    def _extract_value(self, pattern: str, content: str, default: str) -> str:
        """Extract value from markdown using regex pattern"""
        match = re.search(pattern, content)
        return match.group(1).strip() if match else default
    
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
            
            # DEBUG: Show detailed parsing results
            print(f"\n📊 PARSING SUMMARY:")
            print(f"  📚 Lessons found: {len(course_data['weeks'])}")
            print(f"  🛠️  Tools found: {len(course_data['tools'])}")
            print(f"  🎯 Learning outcomes: {len(course_data['learning_outcomes'])}")
            print(f"  📋 Assessment formats: {len(course_data['assessment_formats'])}")
            
            session = self.db_setup.get_session()
            
            # Create main course
            course = Course(
                title=course_data['title'],
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
            
            session.add(course)
            session.flush()
            print(f"\n✅ Created course: {course.title} (ID: {course.id})")
            
            # Create learning outcomes
            learning_outcomes = {}
            for lo_data in course_data['learning_outcomes']:
                lo = LearningOutcome(
                    code=lo_data['code'],
                    description=lo_data['description'],
                    course_id=course.id
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
            lesson_count = 0
            for week_data in course_data['weeks']:
                lesson = Lesson(
                    course_id=course.id,
                    title=f"Week {week_data['week']}: {week_data['topic']}",
                    content=self._build_lesson_content(week_data, course_data),
                    duration=self._estimate_duration(week_data['activity']),
                    order=week_data['week'],
                    activity_type=week_data['activity'],
                    assignment_description=week_data['assignment'],
                    materials_needed=self._get_lesson_materials(week_data),
                    objectives=self._get_lesson_objectives(week_data)
                )
                session.add(lesson)
                session.flush()
                lesson_count += 1
                print(f"  📝 Created lesson: {lesson.title}")
                
                # Link learning outcomes to lesson using the association table
                addressed_outcomes = self.map_learning_outcomes_to_lessons(week_data)
                for lo_code in addressed_outcomes:
                    if lo_code in learning_outcomes:
                        # Use the association table directly
                        stmt = lesson_learning_outcome.insert().values(
                            lesson_id=lesson.id,
                            learning_outcome_id=learning_outcomes[lo_code].id,
                            strength='Primary'
                        )
                        session.execute(stmt)
            
            session.commit()
            print(f"\n🎉 Successfully injected comprehensive course!")
            print(f"📊 Course: {course.title}")
            print(f"🔗 Code: {course.course_code}")
            print(f"🎯 Learning Outcomes: {len(learning_outcomes)}")
            print(f"📋 Assessment Formats: {len(course_data['assessment_formats'])}")
            print(f"🛠️  Tools: {len(course_data['tools'])}")
            print(f"📚 Lessons: {lesson_count}")
            
            session.close()
            return True
            
        except Exception as e:
            print(f"❌ Error injecting course: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_lesson_objectives(self, week_data: Dict[str, Any]) -> str:
        """Generate lesson objectives based on topic and activity"""
        topic = week_data['topic'].lower()
        activity = week_data['activity'].lower()
        
        if 'introduction' in topic:
            return "Understand course structure, Define personal goals, Establish learning expectations"
        elif 'sector' in topic:
            return "Analyze industry opportunities, Identify career paths, Research market trends"
        elif 'studio' in topic or 'digital' in topic:
            return "Configure workspace, Understand ergonomics, Setup required tools"
        elif 'swot' in topic:
            return "Conduct self-assessment, Identify strengths/weaknesses, Develop improvement plan"
        elif 'cv' in topic or 'portfolio' in topic:
            return "Create professional documents, Showcase skills and projects, Develop personal brand"
        elif 'networking' in topic or 'communication' in topic:
            return "Develop communication skills, Build professional network, Practice networking techniques"
        elif 'interview' in topic:
            return "Prepare for interviews, Practice responses, Develop confidence"
        elif 'freelance' in topic or 'corporate' in topic:
            return "Compare career paths, Understand business models, Evaluate opportunities"
        elif 'final' in topic:
            return "Synthesize learning, Present career strategy, Demonstrate professional readiness"
        else:
            return f"Complete {week_data['assignment']}, Participate in {activity}, Understand {topic}"
    
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
    
    injector = CourseInjector()
    success = injector.inject_comprehensive_course(md_file_path)
    
    if success:
        print("\n🚀 Course injection completed!")
        print("\nNext steps:")
        print("1. Verify: python main.py list courses")
        print("2. Generate: python main.py generate --course-id 1 --format all")
    else:
        print("\n❌ Injection failed")


if __name__ == "__main__":
    main()