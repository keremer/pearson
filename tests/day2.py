#!/usr/bin/env python3
"""
Day 2 Test Script - Template System
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("🎯 COURSE AUTOMATION SYSTEM - DAY 2")
    print("=" * 60)
    
    # Step 1: Test Template System
    print("\n📝 STEP 1: Template System Test")
    print("-" * 30)
    
    try:
        from app.reports.template_manager import main as template_main
        template_main()
    except Exception as e:
        print(f"❌ Template system test failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Generate Real Course Materials
    print("\n📚 STEP 2: Generate Real Course Materials")
    print("-" * 30)
    
    try:
        from app.cli.setup import DatabaseSetup
        from app.reports.template_manager import TemplateManager, CourseDataBuilder
        from app.models import Course, Lesson  # <-- Import models directly
        
        # Initialize components
        db_setup = DatabaseSetup()
        template_manager = TemplateManager("app/templates")
        data_builder = CourseDataBuilder(template_manager)
        
        # Get course data from database
        session = db_setup.Session()
        courses = session.query(Course).all()
        
        for course in courses:
            print(f"Generating materials for: {course.title}")
            
            # Get lessons for this course
            lessons = session.query(Lesson).filter_by(course_id=course.id).order_by(Lesson.order).all()
            
            # Build data and generate materials
            course_data = data_builder.build_course_data(course, lessons)
            
            # Generate syllabus
            syllabus_content = template_manager.render_syllabus(course_data)
            syllabus_file = template_manager.save_to_file(
                syllabus_content, 
                f"syllabus_{course.course_code}.md"
            )
            print(f"  ✅ Syllabus: {syllabus_file}")
            
            # Generate course overview
            overview_content = template_manager.render_course_overview(course_data)
            overview_file = template_manager.save_to_file(
                overview_content,
                f"overview_{course.course_code}.md"
            )
            print(f"  ✅ Overview: {overview_file}")
            
            # Generate individual lesson plans
            for lesson in lessons:
                lesson_data = data_builder.build_lesson_data(lesson, course)
                lesson_content = template_manager.render_lesson_plan(lesson_data)
                lesson_file = template_manager.save_to_file(
                    lesson_content,
                    f"lesson_{lesson.order}_{course.course_code}.md"
                )
                print(f"  ✅ Lesson {lesson.order}: {lesson_file}")
        
        session.close()
        
    except Exception as e:
        print(f"❌ Real data generation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 3: Verification
    print("\n✅ STEP 3: Verification")
    print("-" * 30)
    
    output_dir = Path("output")
    if output_dir.exists():
        md_files = list(output_dir.glob("*.md"))
        if md_files:
            print("Generated Markdown files:")
            for md_file in md_files:
                print(f"   📄 {md_file.name} ({md_file.stat().st_size} bytes)")
        else:
            print("❌ No Markdown files were generated!")
    else:
        print("❌ Output directory was not created!")
        return
    
    print("\n🎉 DAY 2 COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\nNext steps for Day 3:")
    print("• Create command-line interface (CLI)")
    print("• Add multi-format export (PDF, HTML, Markdown)")
    print("• Implement batch processing")

if __name__ == "__main__":
    main()