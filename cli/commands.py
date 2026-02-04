#!/usr/bin/env python3
"""
CLI Commands for Course Automation System - OPTIMIZED VERSION
"""
import os
import sys
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional


class CLICommands:
    def __init__(self, database_url: str, output_dir: str, verbose: bool = False):
        self.database_url = database_url
        self.output_dir = output_dir
        self.verbose = verbose
        
        # Import components
        from pearson.cli.setup import DatabaseSetup
        from pearson.models import Course, Lesson  # Fixed import
        
        # Import reports and exporters if available
        try:
            from pearson.reports.template_manager import TemplateManager, CourseDataBuilder
            from pearson.reports.multi_exporter import MultiExporter
            self.template_manager = TemplateManager()
            self.data_builder = CourseDataBuilder(self.template_manager)
            self.exporter = MultiExporter(output_dir)
            self._has_exporters = True
        except ImportError:
            print("⚠️  Exporters not available - generation features limited")
            self._has_exporters = False
        
        self.db_setup = DatabaseSetup(database_url)
        self.Course = Course
        self.Lesson = Lesson
    
    def generate_materials(self, course_id: Optional[int] = None, lesson_id: Optional[int] = None, 
                         formats: Optional[List[str]] = None, templates: Optional[List[str]] = None,
                         batch: bool = False) -> bool:
        """Generate course materials"""
        if not self._has_exporters:
            print("❌ Export components not available. Cannot generate materials.")
            return False
            
        # Provide defaults for optional lists
        if formats is None:
            formats = ['markdown']
        if templates is None:
            templates = ['all']
            
        if self.verbose:
            print(f"🔧 Generating materials: course_id={course_id}, lesson_id={lesson_id}, "
                  f"formats={formats}, templates={templates}, batch={batch}")
        
        try:
            session = self.db_setup.get_session()
            
            if batch:
                courses = session.query(self.Course).all()
                results = []
                
                for course in courses:
                    if self.verbose:
                        print(f"📚 Processing course: {course.title} (ID: {course.id})")
                    
                    result = self._generate_course_materials(
                        course, session, formats, templates
                    )
                    results.append(result)
                
                session.close()
                
                successful = sum(1 for r in results if r)
                print(f"✅ Batch generation completed: {successful}/{len(results)} courses successful")
                return successful > 0
                
            elif course_id:
                course = session.query(self.Course).filter_by(id=course_id).first()
                if not course:
                    print(f"❌ Course with ID {course_id} not found!")
                    session.close()
                    return False
                
                if lesson_id:
                    result = self._generate_lesson_materials(lesson_id, course, session, formats)
                else:
                    result = self._generate_course_materials(course, session, formats, templates)
                
                session.close()
                return result
            else:
                print("❌ Please specify --course-id or use --batch for all courses")
                session.close()
                return False
                
        except Exception as e:
            print(f"❌ Error generating materials: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def list_items(self, what: str, course_id: Optional[int] = None, detailed: bool = False) -> bool:
        """List database items"""
        try:
            session = self.db_setup.get_session()
            
            if what in ['courses', 'all']:
                courses = session.query(self.Course).all()
                print("\n📚 COURSES:")
                print("-" * 60)
                for course in courses:
                    lesson_count = session.query(self.Lesson).filter_by(course_id=course.id).count()
                    print(f"ID: {course.id} | {course.title}")
                    print(f"   Code: {course.course_code} | Instructor: {course.instructor}")
                    print(f"   Lessons: {lesson_count}")
                    if detailed and hasattr(course, "description") and course.description is not None:
                        print(f"   Description: {course.description[:100]}...")
                    print()
            
            if what in ['lessons', 'all'] and course_id:
                lessons = session.query(self.Lesson).filter_by(course_id=course_id).order_by(self.Lesson.order).all()
                course = session.query(self.Course).filter_by(id=course_id).first()
                
                course_title = course.title if course else 'Unknown Course'
                print(f"\n📖 LESSONS for {course_title}:")
                print("-" * 60)
                for lesson in lessons:
                    duration_str = f"{lesson.duration} min" if lesson.duration is not None else "N/A"
                    print(f"ID: {lesson.id} | Lesson {lesson.order}: {lesson.title}")
                    print(f"   Duration: {duration_str}")
                    if detailed and hasattr(lesson, "content") and lesson.content is not None:
                        preview = lesson.content[:100] + '...' if len(str(lesson.content)) > 100 else lesson.content
                        print(f"   Content: {preview}")
                    print()
            elif what in ['lessons', 'all'] and not course_id:
                print("❌ Please specify --course-id to list lessons")
                session.close()
                return False
            
            session.close()
            return True
            
        except Exception as e:
            print(f"❌ Error listing items: {e}")
            return False
    
    def export_data(self, course_id: int, format: str, output: Optional[str] = None) -> bool:
        """Export course data to various formats"""
        try:
            session = self.db_setup.get_session()
            course = session.query(self.Course).filter_by(id=course_id).first()
            
            if not course:
                print(f"❌ Course with ID {course_id} not found!")
                session.close()
                return False
            
            lessons = session.query(self.Lesson).filter_by(course_id=course_id).order_by(self.Lesson.order).all()
            
            # Build export data
            export_data = {
                'course': {
                    'id': course.id,
                    'title': course.title,
                    'code': course.course_code or '',
                    'description': course.description or '',
                    'instructor': course.instructor or '',
                    'created_date': course.created_date.isoformat() if getattr(course, 'created_date', None) is not None else None
                },
                'lessons': [
                    {
                        'id': lesson.id,
                        'order': lesson.order,
                        'title': lesson.title,
                        'content': lesson.content or '',
                        'duration': lesson.duration,
                        'created_date': lesson.created_date.isoformat() if lesson.created_date is not None else None
                    }
                    for lesson in lessons
                ],
                'metadata': {
                    'exported_at': self._current_timestamp(),
                    'total_lessons': len(lessons),
                    'total_duration': sum(lesson.duration or 0 for lesson in lessons)
                }
            }
            
            if not output:
                course_code = course.course_code or f"course_{course_id}"
                safe_course_code = "".join(str(c) for c in course_code if str(c).isalnum() or c in ('-', '_'))
                output = f"course_export_{safe_course_code}.{format}"
            
            if format == 'json':
                with open(output, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            elif format == 'csv':
                with open(output, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Order', 'Title', 'Duration', 'Content Preview'])
                    for lesson in lessons:
                        content_str = str(lesson.content) if lesson.content is not None else ''
                        content_preview = content_str[:100] + '...' if len(content_str) > 100 else content_str
                        writer.writerow([
                            lesson.order,
                            lesson.title,
                            lesson.duration or '',
                            content_preview
                        ])
            
            elif format == 'excel':
                try:
                    import pandas as pd
                    df = pd.DataFrame([
                        {
                            'Order': lesson.order,
                            'Title': lesson.title,
                            'Duration': lesson.duration or '',
                            'Content': lesson.content or ''
                        }
                        for lesson in lessons
                    ])
                    df.to_excel(output, index=False)
                except ImportError:
                    print("❌ pandas not installed. Install with: pip install pandas")
                    session.close()
                    return False
            
            elif format == 'md':
                with open(output, 'w', encoding='utf-8') as f:
                    f.write(f"# {course.title}\n\n")
                    f.write(f"**Code**: {course.course_code}\n\n")
                    f.write(f"**Instructor**: {course.instructor}\n\n")
                    f.write(f"**Description**: {course.description}\n\n")
                    f.write("## Lessons\n\n")
                    for lesson in lessons:
                        f.write(f"### {lesson.order}. {lesson.title}\n\n")
                        f.write(f"Duration: {lesson.duration or 'N/A'} minutes\n\n")
                        if lesson.content is not None:
                            f.write(f"{lesson.content}\n\n")
            
            session.close()
            print(f"✅ Exported course data to: {output}")
            return True
            
        except Exception as e:
            print(f"❌ Error exporting data: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def _generate_course_materials(self, course, session, formats: List[str], templates: List[str]) -> bool:
        """Generate materials for a single course"""
        if not self._has_exporters:
            return False
            
        try:
            print(f"📝 Generating materials for: {course.title}")
            # Placeholder for actual generation logic
            return True
        except Exception as e:
            print(f"❌ Error generating course materials: {e}")
            return False
    
    def _generate_lesson_materials(self, lesson_id: int, course, session, formats: List[str]) -> bool:
        """Generate materials for a specific lesson"""
        if not self._has_exporters:
            return False
            
        try:
            lesson = session.query(self.Lesson).filter_by(id=lesson_id, course_id=course.id).first()
            if not lesson:
                print(f"❌ Lesson with ID {lesson_id} not found in course {course.title}!")
                return False
            
            print(f"📝 Generating materials for lesson: {lesson.title}")
            # Placeholder for actual generation logic
            return True
            
        except Exception as e:
            print(f"❌ Error generating lesson materials: {e}")
            return False
    
    def _current_timestamp(self) -> str:
        """Get current timestamp for metadata"""
        from datetime import datetime
        return datetime.now().isoformat()