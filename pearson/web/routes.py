#!/usr/bin/env python3
# type: ignore
"""
Flask Routes for Course Management Web Interface
UPDATED FOR NEW PROJECT STRUCTURE
"""
import os
import tempfile
from flask import (render_template, request, redirect, 
                   url_for, flash, g, jsonify, session, current_app)
from pearson.models import Course, Lesson, LearningOutcome, AssessmentFormat, Tool
from cli.setup import DatabaseSetup
from werkzeug.utils import secure_filename
from cli.course_injector import CourseInjector
from web import web_bp
from web.forms import CourseForm, LessonForm, ImportForm


def get_db_session():
    """
    Get database session from g object if it exists,
    otherwise create and store it in g.
    This ensures one session per request.
    """
    if 'db_session' not in g:
        if hasattr(current_app, 'config') and 'db_setup' in current_app.config:
            g.db_session = current_app.config['db_setup'].Session()
        else:
            # Fallback for direct execution
            db_setup = DatabaseSetup('sqlite:///courses.db')
            g.db_session = db_setup.Session()
    
    return g.db_session

@web_bp.before_app_request
def setup_db():
    """
    Ensure database session is available for every request.
    Using before_app_request ensures this runs before each route.
    """
    # Just access g.db_session to trigger creation via get_db_session
    # This is cleaner than duplicating logic here
    get_db_session()

@web_bp.teardown_app_request
def teardown_db(exception=None):
    """
    Close database session at the end of each request.
    This runs even if an error occurred.
    """
    db_session = g.pop('db_session', None)
    if db_session is not None:
        db_session.close()

@web_bp.route('/')
def index():
    """Home page with overview"""
    try:
        db_session = get_db_session()
        courses = db_session.query(Course).all()
        total_lessons = db_session.query(Lesson).count()
        
        stats = {
            'total_courses': len(courses),
            'total_lessons': total_lessons,
            'recent_courses': courses[-3:] if len(courses) > 3 else courses
        }
        
        return render_template('index.html', 
                             stats=stats, 
                             courses=courses)
    except Exception as e:
        flash(f"Database Error: {e}", "error")
        return render_template('index.html', stats={}, courses=[])

@web_bp.route('/courses')
def list_courses():
    """List all courses"""
    try:
        db_session = get_db_session()
        courses = db_session.query(Course).order_by(Course.created_date.desc()).all()
        return render_template('courses.html', courses=courses)
    except Exception as e:
        flash(f'Error loading courses: {str(e)}', 'error')
        return render_template('courses.html', courses=[])

@web_bp.route('/course/<int:course_id>')
def course_detail(course_id):
    """Show course details and lessons"""
    try:
        db_session = get_db_session()
        course = db_session.query(Course).filter_by(id=course_id).first()
        if not course:
            flash('Course not found', 'error')
            return redirect(url_for('web.list_courses'))
        
        lessons = (db_session.query(Lesson)
                  .filter_by(course_id=course_id)
                  .order_by(Lesson.order)
                  .all())
        
        return render_template('course_detail.html', 
                             course=course, 
                             lessons=lessons)
    except Exception as e:
        flash(f'Error loading course: {str(e)}', 'error')
        return redirect(url_for('web.list_courses'))

@web_bp.route('/course/<int:course_id>/lessons')
def course_lessons(course_id):
    """Show lessons for a specific course"""
    try:
        db_session = get_db_session()
        course = db_session.query(Course).filter_by(id=course_id).first()
        if not course:
            flash('Course not found', 'error')
            return redirect(url_for('web.list_courses'))
        
        lessons = (db_session.query(Lesson)
                  .filter_by(course_id=course_id)
                  .order_by(Lesson.order)
                  .all())
        
        return render_template('lessons.html', 
                             course=course, 
                             lessons=lessons)
    except Exception as e:
        flash(f'Error loading lessons: {str(e)}', 'error')
        return redirect(url_for('web.list_courses'))

@web_bp.route('/course/create', methods=['GET', 'POST'])
def create_course():
    """Create a new course"""
    form = CourseForm()
    if form.validate_on_submit():
        # Process form data
        course = Course(
            title=form.title.data,
            course_code=form.course_code.data,
            instructor=form.instructor.data,
            contact_email=form.contact_email.data,
            level=form.level.data,
            language=form.language.data,
            delivery_mode=form.delivery_mode.data,
            aim=form.aim.data,
            description=form.description.data,
            objectives=form.objectives.data
        )
        db_session = get_db_session()
        db_session.add(course)
        db_session.commit()
        flash(f'Course "{course.title}" created successfully!', 'success')
        return redirect(url_for('web.course_detail', course_id=course.id))
    
    if request.method == 'GET':
        return render_template('course_edit.html', course=None)
    
    # POST method
    db_session = get_db_session()
    try:
        course = Course(
            title=request.form['title'],
            course_code=request.form['course_code'],
            instructor=request.form.get('instructor', ''),
            contact_email=request.form.get('contact_email', ''),
            level=request.form.get('level', ''),
            language=request.form.get('language', 'English'),
            delivery_mode=request.form.get('delivery_mode', ''),
            aim=request.form.get('aim', ''),
            description=request.form.get('description', ''),
            objectives=request.form.get('objectives', '')
        )
        
        db_session.add(course)
        db_session.commit()
        flash(f'Course "{course.title}" created successfully!', 'success')
        return redirect(url_for('web.course_detail', course_id=course.id))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error creating course: {str(e)}', 'error')
        return render_template('course_edit.html', form=form, course=None)

@web_bp.route('/course/<int:course_id>/edit', methods=['GET', 'POST'])
def edit_course(course_id):
    """Edit an existing course"""
    db_session = get_db_session()
    course = db_session.query(Course).filter_by(id=course_id).first()
    
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('web.list_courses'))
    
    if request.method == 'GET':
        return render_template('course_edit.html', course=course)
    
    # POST method
    try:
        course.title = request.form['title']
        course.course_code = request.form['course_code']
        course.instructor = request.form.get('instructor', '')
        course.contact_email = request.form.get('contact_email', '')
        course.level = request.form.get('level', '')
        course.language = request.form.get('language', 'English')
        course.delivery_mode = request.form.get('delivery_mode', '')
        course.aim = request.form.get('aim', '')
        course.description = request.form.get('description', '')
        course.objectives = request.form.get('objectives', '')
        
        db_session.commit()
        flash(f'Course "{course.title}" updated successfully!', 'success')
        return redirect(url_for('web.course_detail', course_id=course.id))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error updating course: {str(e)}', 'error')
        return render_template('course_edit.html', course=course)

@web_bp.route('/course/<int:course_id>/delete', methods=['POST'])
def delete_course(course_id):
    """Delete a course"""
    db_session = get_db_session()
    try:
        course = db_session.query(Course).filter_by(id=course_id).first()
        if course:
            course_title = course.title
            db_session.delete(course)
            db_session.commit()
            flash(f'Course "{course_title}" deleted successfully!', 'success')
        else:
            flash('Course not found', 'error')
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting course: {str(e)}', 'error')
    
    return redirect(url_for('web.list_courses'))

@web_bp.route('/course/<int:course_id>/lesson/create', methods=['GET', 'POST'])
def create_lesson(course_id):
    """Create a new lesson for a course"""
    db_session = get_db_session()
    course = db_session.query(Course).filter_by(id=course_id).first()
    
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('web.list_courses'))
    
    if request.method == 'GET':
        return render_template('lesson_edit.html', course=course, lesson=None)
    
    # POST method
    try:
        # Validate order is integer
        try:
            order = int(request.form.get('order', 1))
        except ValueError:
            order = 1
            
        try:
            duration = int(request.form.get('duration', 60))
        except ValueError:
            duration = 60
            
        lesson = Lesson(
            course_id=course_id,
            title=request.form['title'],
            content=request.form.get('content', ''),
            duration=duration,
            order=order,
            activity_type=request.form.get('activity_type', ''),
            assignment_description=request.form.get('assignment_description', ''),
            materials_needed=request.form.get('materials_needed', '')
        )
        
        db_session.add(lesson)
        db_session.commit()
        flash(f'Lesson "{lesson.title}" created successfully!', 'success')
        return redirect(url_for('web.course_lessons', course_id=course_id))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error creating lesson: {str(e)}', 'error')
        return render_template('lesson_edit.html', course=course, lesson=None)

@web_bp.route('/lesson/<int:lesson_id>/edit', methods=['GET', 'POST'])
def edit_lesson(lesson_id):
    """Edit an existing lesson"""
    db_session = get_db_session()
    lesson = db_session.query(Lesson).filter_by(id=lesson_id).first()
    
    if not lesson:
        flash('Lesson not found', 'error')
        return redirect(url_for('web.list_courses'))
    
    course = db_session.query(Course).filter_by(id=lesson.course_id).first()
    
    if request.method == 'GET':
        return render_template('lesson_edit.html', course=course, lesson=lesson)
    
    # POST method
    try:
        # Validate numeric fields
        try:
            lesson.order = int(request.form.get('order', 1))
        except ValueError:
            pass  # Keep existing value
            
        try:
            lesson.duration = int(request.form.get('duration', 60))
        except ValueError:
            pass  # Keep existing value
            
        lesson.title = request.form['title']
        lesson.content = request.form.get('content', '')
        lesson.activity_type = request.form.get('activity_type', '')
        lesson.assignment_description = request.form.get('assignment_description', '')
        lesson.materials_needed = request.form.get('materials_needed', '')
        
        db_session.commit()
        flash(f'Lesson "{lesson.title}" updated successfully!', 'success')
        return redirect(url_for('web.course_lessons', course_id=lesson.course_id))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error updating lesson: {str(e)}', 'error')
        return render_template('lesson_edit.html', course=course, lesson=lesson)

@web_bp.route('/lesson/<int:lesson_id>/delete', methods=['POST'])
def delete_lesson(lesson_id):
    """Delete a lesson"""
    db_session = get_db_session()
    try:
        lesson = db_session.query(Lesson).filter_by(id=lesson_id).first()
        if lesson:
            course_id = lesson.course_id
            lesson_title = lesson.title
            db_session.delete(lesson)
            db_session.commit()
            flash(f'Lesson "{lesson_title}" deleted successfully!', 'success')
            return redirect(url_for('web.course_lessons', course_id=course_id))
        else:
            flash('Lesson not found', 'error')
    except Exception as e:
        db_session.rollback()
        flash(f'Error deleting lesson: {str(e)}', 'error')
    
    return redirect(url_for('web.list_courses'))

@web_bp.route('/course/import', methods=['GET', 'POST'])
def import_syllabus():
    """Handle Markdown file uploads and trigger CourseInjector."""
    if request.method == 'GET':
        return render_template('import.html')
    
    # POST method
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(request.url)
    
    if not file.filename.endswith('.md'):
        flash('Please upload a valid Markdown (.md) file.', 'error')
        return redirect(request.url)

    # Create temp directory if it doesn't exist
    temp_dir = os.path.join(current_app.instance_path, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Save temporarily
    filename = secure_filename(file.filename)
    temp_path = os.path.join(temp_dir, filename)
    
    try:
        file.save(temp_path)
        
        # Use existing CourseInjector
        database_url = current_app.config.get('DATABASE_URL', 'sqlite:///courses.db')
        injector = CourseInjector(database_url)
        success = injector.inject_comprehensive_course(temp_path)
        
        if success:
            flash(f'Successfully imported course from {filename}!', 'success')
            return redirect(url_for('web.list_courses'))
        else:
            flash('Parsing failed. Ensure the Markdown follows the required schema.', 'error')
            return redirect(request.url)
            
    except Exception as e:
        flash(f'Import error: {str(e)}', 'error')
        return redirect(request.url)
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

# API endpoints for potential AJAX functionality
@web_bp.route('/api/courses')
def api_courses():
    """JSON API for courses"""
    try:
        db_session = get_db_session()
        courses = db_session.query(Course).all()
        courses_data = [{
            'id': course.id,
            'title': course.title,
            'code': course.course_code,
            'instructor': course.instructor,
            'lesson_count': len(course.lessons)
        } for course in courses]
        
        return jsonify(courses_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@web_bp.route('/api/course/<int:course_id>/lessons')
def api_course_lessons(course_id):
    """JSON API for course lessons"""
    try:
        db_session = get_db_session()
        lessons = (db_session.query(Lesson)
                  .filter_by(course_id=course_id)
                  .order_by(Lesson.order)
                  .all())
        
        lessons_data = [{
            'id': lesson.id,
            'title': lesson.title,
            'order': lesson.order,
            'duration': lesson.duration,
            'activity_type': lesson.activity_type
        } for lesson in lessons]
        
        return jsonify(lessons_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500