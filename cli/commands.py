#!/usr/bin/env python3
"""
CLI Commands for Course Automation System - OPTIMIZED VERSION
Updated for new project structure
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
        
        # Import components - FIXED for new structure
        from cli.setup import DatabaseSetup
        from shared.models import Course, Lesson
        
        # Import reports and exporters if available
        try:
            from reports.template_manager import TemplateManager, CourseDataBuilder
            from reports.multi_exporter import MultiExporter
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
            session = self.db_setup.Session()
            
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
    
    def _generate_course_materials(self, course, session, formats: List[str], templates: List[str]) -> bool:
        """Generate materials for a single course"""
        if not self._has_exporters:
            return False
            
        try:
            lessons = session.query(self.Lesson).filter_by(course_id=course.id).order_by(self.Lesson.order).all()
            course_data = self.data_builder.build_course_data(course, lessons)
            
            templates_to_generate = set(templates)
            if 'all' in templates_to_generate:
                templates_to_generate = {'syllabus', 'overview', 'lesson'}
            
            generated_files = []
            
            if 'syllabus' in templates_to_generate:
                syllabus_content = self.template_manager.render_syllabus(course_data)
                files = self.exporter.export_content(
                    syllabus_content, 
                    f"syllabus_{course.course_code}", 
                    formats
                )
                if files:
                    generated_files.extend(files)
                if self.verbose:
                    print(f"  ✅ Syllabus: {len(files)} files")
            
            if 'overview' in templates_to_generate:
                overview_content = self.template_manager.render_course_overview(course_data)
                files = self.exporter.export_content(
                    overview_content,
                    f"overview_{course.course_code}",
                    formats
                )
                if files:
                    generated_files.extend(files)
                if self.verbose:
                    print(f"  ✅ Overview: {len(files)} files")
            
            if 'lesson' in templates_to_generate:
                for lesson in lessons:
                    lesson_data = self.data_builder.build_lesson_data(lesson, course)
                    lesson_content = self.template_manager.render_lesson_plan(lesson_data)
                    files = self.exporter.export_content(
                        lesson_content,
                        f"lesson_{lesson.order}_{course.course_code}",
                        formats
                    )
                    if files:
                        generated_files.extend(files)
                
                if self.verbose:
                    print(f"  ✅ Lessons: {len(lessons)} lessons")
            
            print(f"✅ Generated {len(generated_files)} files for {course.title}")
            return True
            
        except Exception as e:
            print(f"❌ Error generating course materials: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
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
            
            lesson_data = self.data_builder.build_lesson_data(lesson, course)
            lesson_content = self.template_manager.render_lesson_plan(lesson_data)
            
            files = self.exporter.export_content(
                lesson_content,
                f"lesson_{lesson.order}_{course.course_code}",
                formats
            )
            
            if files:
                print(f"✅ Generated {len(files)} files for lesson: {lesson.title}")
                return True
            else:
                print(f"❌ No files generated for lesson: {lesson.title}")
                return False
            
        except Exception as e:
            print(f"❌ Error generating lesson materials: {e}")
            return False
            
    def list_items(self, what: str, course_id: Optional[int] = None, detailed: bool = False) -> bool:
        """List courses or lessons"""
        try:
            session = self.db_setup.Session()
            
            if what in ['courses', 'all']:
                courses = session.query(self.Course).all()
                print("\n📚 COURSES:")
                print("-" * 60)
                for course in courses:
                    lesson_count = session.query(self.Lesson).filter_by(course_id=course.id).count()
                    print(f"ID: {course.id} | {course.title}")
                    print(f"   Code: {course.course_code} | Instructor: {course.instructor}")
                    print(f"   Lessons: {lesson_count} | Created: {course.created_date.date()}")
                    if detailed and getattr(course, "description", None):
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
                    print(f"   Duration: {duration_str} | Created: {lesson.created_date.date()}")
                    if detailed and getattr(lesson, "content", None):
                        content_value = getattr(lesson, "content", "")
                        preview = content_value[:100] + '...' if len(content_value) > 100 else content_value
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
            session = self.db_setup.Session()
            course = session.query(self.Course).filter_by(id=course_id).first()
            
            if not course:
                print(f"❌ Course with ID {course_id} not found!")
                session.close()
                return False
            
            lessons = session.query(self.Lesson).filter_by(course_id=course_id).order_by(self.Lesson.order).all()
            
            # Safe data building
            export_data = {
                'course': {
                    'id': course.id,
                    'title': course.title,
                    'code': course.course_code or '',
                    'description': course.description or '',
                    'instructor': course.instructor or '',
                    'contact_email': course.contact_email or '',
                    'objectives': course.objectives or '',
                    'created_date': course.created_date.isoformat() if course.created_date is not None else None
                },
                'lessons': [
                    {
                        'id': lesson.id,
                        'order': lesson.order,
                        'title': lesson.title,
                        'content': lesson.content or '',
                        'duration': lesson.duration,
                        'objectives': lesson.objectives or '',
                        'materials_needed': lesson.materials_needed or '',
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
                course_code_value = getattr(course, "course_code", None)
                if course_code_value is not None and str(course_code_value).strip() != "":
                    safe_course_code = "".join(c for c in str(course_code_value) if c.isalnum() or c in ('-', '_'))
                else:
                    safe_course_code = f"course_{course_id}"
                output = f"course_export_{safe_course_code}.{format}"
            
            if format == 'json':
                with open(output, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            elif format == 'yaml':
                try:
                    import yaml
                    with open(output, 'w', encoding='utf-8') as f:
                        yaml.dump(export_data, f, default_flow_style=False, allow_unicode=True)
                except ImportError:
                    print("❌ PyYAML not installed. Install with: pip install PyYAML")
                    session.close()
                    return False
            
            elif format == 'csv':
                with open(output, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Order', 'Title', 'Duration', 'Objectives', 'Content Preview'])
                    for lesson in lessons:
                        content_value = getattr(lesson, "content", "") or ""
                        content_preview = content_value[:100] + '...' if content_value and len(content_value) > 100 else content_value
                        writer.writerow([
                            lesson.order,
                            lesson.title,
                            lesson.duration or '',
                            lesson.objectives or '',
                            content_preview
                        ])
            
            session.close()
            print(f"✅ Exported course data to: {output}")
            return True
            
        except Exception as e:
            print(f"❌ Error exporting data: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def _current_timestamp(self) -> str:
        """Get current timestamp for metadata"""
        from datetime import datetime
        return datetime.now().isoformat()