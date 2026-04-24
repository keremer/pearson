#!/usr/bin/env python3
"""
CLI Commands for Course Automation System
Fully Integrated with crminaec Flask-SQLAlchemy Architecture
"""
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import the core application and unified models
from crminaec import create_app
from crminaec.core.models import db
from crminaec.platforms.emek.models import Item, ItemComposition


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
                    courses = db.session.scalars(db.select(Item).filter_by(item_type='course')).all()
                    results = []
                    
                    for course in courses:
                        if self.verbose:
                            print(f"📚 Processing course: {course.name} (ID: {course.item_id})")
                        
                        result = self._generate_course_materials(course, formats, templates)
                        results.append(result)
                    
                    successful = sum(1 for r in results if r)
                    print(f"✅ Batch generation completed: {successful}/{len(results)} courses successful")
                    return successful > 0
                    
                elif course_id:
                    course = db.session.scalar(db.select(Item).filter_by(item_id=course_id, item_type='course'))
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
                    courses = db.session.scalars(db.select(Item).filter_by(item_type='course')).all()
                    print("\n📚 COURSES:")
                    print("-" * 60)
                    for course in courses:
                        lesson_count = len([c for c in course.children_links if c.child_item.item_type == 'lesson'])
                        specs = course.technical_specs or {}
                        print(f"ID: {course.item_id} | {course.name}")
                        print(f"   Code: {course.code} | Instructor: {specs.get('instructor', 'N/A')}")
                        print(f"   Lessons: {lesson_count}")
                        if detailed and specs.get('description'):
                            desc = specs['description']
                            print(f"   Description: {desc[:100]}...")
                        print()
                
                if what in ['lessons', 'all'] and course_id:
                    course = db.session.scalar(db.select(Item).filter_by(item_id=course_id, item_type='course'))
                    
                    if not course:
                        print(f"❌ Course {course_id} not found.")
                        return False

                    comps = db.session.scalars(db.select(ItemComposition).filter_by(parent_id=course.item_id).order_by(ItemComposition.sort_order)).all()
                    lessons = [(c.child_item, c.sort_order) for c in comps if c.child_item.item_type == 'lesson']
                    course_title = course.name
                    
                    print(f"\n📖 LESSONS for {course_title}:")
                    print("-" * 60)
                    for lesson, order in lessons:
                        specs = lesson.technical_specs or {}
                        duration_str = f"{specs.get('duration', 60)} min"
                        print(f"ID: {lesson.item_id} | Lesson {order}: {lesson.name}")
                        print(f"   Duration: {duration_str}")
                        if detailed and specs.get('content'):
                            content = specs['content']
                            preview = content[:100] + '...' if len(content) > 100 else content
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
                course = db.session.scalar(db.select(Item).filter_by(item_id=course_id, item_type='course'))
                
                if not course:
                    print(f"❌ Course with ID {course_id} not found!")
                    return False
                
                comps = db.session.scalars(db.select(ItemComposition).filter_by(parent_id=course.item_id).order_by(ItemComposition.sort_order)).all()
                lessons = [(c.child_item, c.sort_order) for c in comps if c.child_item.item_type == 'lesson']
                
                specs = course.technical_specs or {}
                # Build export data using the new DataClass attributes
                export_data = {
                    'course': {
                        'id': course.item_id,
                        'title': course.name,
                        'code': course.code or '',
                        'description': specs.get('description', ''),
                        'instructor': specs.get('instructor', '')
                    },
                    'lessons': [
                        {
                            'id': lesson.item_id,
                            'order': order,
                            'title': lesson.name,
                            'content': (lesson.technical_specs or {}).get('content', ''),
                            'duration': (lesson.technical_specs or {}).get('duration', 60)
                        }
                        for lesson, order in lessons
                    ],
                    'metadata': {
                        'exported_at': datetime.now().isoformat(),
                        'total_lessons': len(lessons),
                        'total_duration': sum((l.technical_specs or {}).get('duration', 60) for l, _ in lessons)
                    }
                }
                
                if not output:
                    course_code = course.code or f"course_{course_id}"
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
                        for lesson, order in lessons:
                            content_str = str((lesson.technical_specs or {}).get('content', ''))
                            content_preview = content_str[:100] + '...' if len(content_str) > 100 else content_str
                            writer.writerow([
                                order, lesson.name, (lesson.technical_specs or {}).get('duration', ''), content_preview
                            ])
                
                elif format == 'excel':
                    try:
                        import pandas as pd
                        df = pd.DataFrame([
                            {
                                'Order': order,
                                'Title': lesson.name,
                                'Duration': (lesson.technical_specs or {}).get('duration', ''),
                                'Content': (lesson.technical_specs or {}).get('content', '')
                            }
                            for lesson, order in lessons
                        ])
                        df.to_excel(output, index=False)
                    except ImportError:
                        print("❌ pandas not installed. Install with: pip install pandas")
                        return False
                
                elif format == 'md':
                    with open(output, 'w', encoding='utf-8') as f:
                        f.write(f"# {course.name}\n\n")
                        f.write(f"**Code**: {course.code}\n\n")
                        f.write(f"**Instructor**: {specs.get('instructor', 'N/A')}\n\n")
                        f.write(f"**Description**: {specs.get('description', '')}\n\n")
                        f.write("## Lessons\n\n")
                        for lesson, order in lessons:
                            f.write(f"### {order}. {lesson.name}\n\n")
                            f.write(f"Duration: {(lesson.technical_specs or {}).get('duration', 'N/A')} minutes\n\n")
                            if (lesson.technical_specs or {}).get('content'):
                                f.write(f"{(lesson.technical_specs or {}).get('content')}\n\n")
                
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
            print(f"📝 Generating materials for: {course.name}")
            return True
        except Exception as e:
            print(f"❌ Error generating course materials: {e}")
            return False
    
    def _generate_lesson_materials(self, lesson_id: int, course, formats: List[str]) -> bool:
        """Generate materials for a specific lesson"""
        if not self._has_exporters: return False
        try:
            comp = db.session.scalar(db.select(ItemComposition).filter_by(child_id=lesson_id, parent_id=course.item_id))
            if not comp:
                print(f"❌ Lesson {lesson_id} not found in {course.name}!")
                return False
            
            print(f"📝 Generating materials for lesson: {comp.child_item.name}")
            return True
        except Exception as e:
            print(f"❌ Error generating lesson materials: {e}")
            return False