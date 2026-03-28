#!/usr/bin/env python3
"""
CLI Commands for Course Automation System
Fully Integrated with crminaec Flask-SQLAlchemy Architecture
"""
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# Import the core application and unified models
from crminaec import create_app
from crminaec.core.models import db, Course, Lesson

class CLICommands:
    def __init__(self, database_url: str = ""
                 "", output_dir: str = 'output', verbose: bool = False):
        self.output_dir = output_dir
        self.verbose = verbose
        
        # We use the Flask app factory instead of direct DB urls
        self.app = create_app()
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        # Import reports and exporters if available
        try:
            from crminaec.core.reporting.multi_exporter import MultiExporter
            from crminaec.core.reporting.template_manager import (
                CourseDataBuilder, TemplateManager)
            self.template_manager = TemplateManager()
            self.data_builder = CourseDataBuilder(self.template_manager)
            self.exporter = MultiExporter(output_dir)
            self._has_exporters = True
        except ImportError:
            if self.verbose:
                print("⚠️  Exporters not available - generation features limited")
            self._has_exporters = False
    
    def generate_materials(self, course_id: Optional[int] = None, lesson_id: Optional[int] = None, 
                           formats: Optional[List[str]] = None, templates: Optional[List[str]] = None,
                           batch: bool = False) -> bool:
        """Generate course materials"""
        if not self._has_exporters:
            print("❌ Export components not available. Cannot generate materials.")
            return False
            
        formats = formats or ['markdown']
        templates = templates or ['all']
            
        if self.verbose:
            print(f"🔧 Generating materials: course_id={course_id}, lesson_id={lesson_id}, "
                  f"formats={formats}, templates={templates}, batch={batch}")
        
        try:
            with self.app.app_context():
                if batch:
                    courses = db.session.query(Course).all()
                    results = []
                    
                    for course in courses:
                        if self.verbose:
                            print(f"📚 Processing course: {course.course_title} (ID: {course.course_id})")
                        
                        result = self._generate_course_materials(course, formats, templates)
                        results.append(result)
                    
                    successful = sum(1 for r in results if r)
                    print(f"✅ Batch generation completed: {successful}/{len(results)} courses successful")
                    return successful > 0
                    
                elif course_id:
                    course = db.session.query(Course).filter_by(course_id=course_id).first()
                    if not course:
                        print(f"❌ Course with ID {course_id} not found!")
                        return False
                    
                    if lesson_id:
                        return self._generate_lesson_materials(lesson_id, course, formats)
                    else:
                        return self._generate_course_materials(course, formats, templates)
                else:
                    print("❌ Please specify --course-id or use --batch for all courses")
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
            with self.app.app_context():
                if what in ['courses', 'all']:
                    courses = db.session.query(Course).all()
                    print("\n📚 COURSES:")
                    print("-" * 60)
                    for course in courses:
                        # Use our new mapped fields (course.lessons list)
                        lesson_count = len(course.lessons)
                        print(f"ID: {course.course_id} | {course.course_title}")
                        print(f"   Code: {course.course_code} | Instructor: {course.instructor}")
                        print(f"   Lessons: {lesson_count}")
                        if detailed and course.description:
                            print(f"   Description: {course.description[:100]}...")
                        print()
                
                if what in ['lessons', 'all'] and course_id:
                    course = db.session.query(Course).filter_by(course_id=course_id).first()
                    
                    if not course:
                        print(f"❌ Course {course_id} not found.")
                        return False

                    # SQLAlchemy already orders lessons via the model definition
                    lessons = course.lessons 
                    course_title = course.course_title
                    
                    print(f"\n📖 LESSONS for {course_title}:")
                    print("-" * 60)
                    for lesson in lessons:
                        duration_str = f"{lesson.duration} min" if lesson.duration else "N/A"
                        print(f"ID: {lesson.lesson_id} | Lesson {lesson.order}: {lesson.lesson_title}")
                        print(f"   Duration: {duration_str}")
                        if detailed and lesson.content:
                            preview = lesson.content[:100] + '...' if len(lesson.content) > 100 else lesson.content
                            print(f"   Content: {preview}")
                        print()
                        
                elif what in ['lessons', 'all'] and not course_id:
                    print("❌ Please specify --course-id to list lessons")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error listing items: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def export_data(self, course_id: int, format: str, output: Optional[str] = None) -> bool:
        """Export course data to various formats"""
        try:
            with self.app.app_context():
                course = db.session.query(Course).filter_by(course_id=course_id).first()
                
                if not course:
                    print(f"❌ Course with ID {course_id} not found!")
                    return False
                
                # Fetch lessons utilizing the sorted relationship mapping
                lessons = course.lessons
                
                # Build export data using the new DataClass attributes
                export_data = {
                    'course': {
                        'id': course.course_id,
                        'title': course.course_title,
                        'code': course.course_code or '',
                        'description': course.description or '',
                        'instructor': course.instructor or '',
                        'created_date': course.created_date.isoformat() if course.created_date else None
                    },
                    'lessons': [
                        {
                            'id': lesson.lesson_id,
                            'order': lesson.order,
                            'title': lesson.lesson_title,
                            'content': lesson.content or '',
                            'duration': lesson.duration,
                            'created_date': lesson.created_date.isoformat() if lesson.created_date else None
                        }
                        for lesson in lessons
                    ],
                    'metadata': {
                        'exported_at': datetime.now().isoformat(),
                        'total_lessons': len(lessons),
                        'total_duration': sum(lesson.duration or 0 for lesson in lessons)
                    }
                }
                
                if not output:
                    course_code = course.course_code or f"course_{course_id}"
                    safe_course_code = "".join(str(c) for c in course_code if str(c).isalnum() or c in ('-', '_'))
                    # Path resolution for output dir
                    output = str(Path(self.output_dir) / f"course_export_{safe_course_code}.{format}")
                
                if format == 'json':
                    with open(output, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                elif format == 'csv':
                    with open(output, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Order', 'Title', 'Duration', 'Content Preview'])
                        for lesson in lessons:
                            content_str = str(lesson.content) if lesson.content else ''
                            content_preview = content_str[:100] + '...' if len(content_str) > 100 else content_str
                            writer.writerow([
                                lesson.order, lesson.lesson_title, lesson.duration or '', content_preview
                            ])
                
                elif format == 'excel':
                    try:
                        import pandas as pd
                        df = pd.DataFrame([
                            {
                                'Order': lesson.order,
                                'Title': lesson.lesson_title,
                                'Duration': lesson.duration or '',
                                'Content': lesson.content or ''
                            }
                            for lesson in lessons
                        ])
                        df.to_excel(output, index=False)
                    except ImportError:
                        print("❌ pandas not installed. Install with: pip install pandas")
                        return False
                
                elif format == 'md':
                    with open(output, 'w', encoding='utf-8') as f:
                        f.write(f"# {course.course_title}\n\n")
                        f.write(f"**Code**: {course.course_code}\n\n")
                        f.write(f"**Instructor**: {course.instructor}\n\n")
                        f.write(f"**Description**: {course.description}\n\n")
                        f.write("## Lessons\n\n")
                        for lesson in lessons:
                            f.write(f"### {lesson.order}. {lesson.lesson_title}\n\n")
                            f.write(f"Duration: {lesson.duration or 'N/A'} minutes\n\n")
                            if lesson.content:
                                f.write(f"{lesson.content}\n\n")
                
                print(f"✅ Exported course data to: {output}")
                return True
                
        except Exception as e:
            print(f"❌ Error exporting data: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    # Note: Removed the unused 'session' arguments as they are managed via context.
    def _generate_course_materials(self, course, formats: List[str], templates: List[str]) -> bool:
        """Generate materials for a single course"""
        if not self._has_exporters: return False
        try:
            print(f"📝 Generating materials for: {course.course_title}")
            return True
        except Exception as e:
            print(f"❌ Error generating course materials: {e}")
            return False
    
    def _generate_lesson_materials(self, lesson_id: int, course, formats: List[str]) -> bool:
        """Generate materials for a specific lesson"""
        if not self._has_exporters: return False
        try:
            lesson = db.session.query(Lesson).filter_by(lesson_id=lesson_id, course_id=course.course_id).first()
            if not lesson:
                print(f"❌ Lesson {lesson_id} not found in {course.course_title}!")
                return False
            
            print(f"📝 Generating materials for lesson: {lesson.lesson_title}")
            return True
        except Exception as e:
            print(f"❌ Error generating lesson materials: {e}")
            return False