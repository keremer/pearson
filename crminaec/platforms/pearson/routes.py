#!/usr/bin/env python3
"""
Flask Routes for Course Management Web Interface (Pearson Platform)
Fully Integrated with crminaec Data-First Architecture
"""
import os
import tempfile

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from werkzeug.utils import secure_filename

# You no longer need to import pearson_bp from crminaec.web, 
# it was already defined in crminaec/__init__.py, but standard practice is 
# to import it from the __init__ or define it here. Since you are registering it in
# __init__.py, let's just make sure we export it from this file correctly.
from crminaec import pearson_bp
# Fix Imports for new architecture
from crminaec.cli.course_injector import CourseInjector
# Google Interop Imports
from crminaec.core.interop.google_docs.client import GoogleDocsClient
from crminaec.core.interop.google_docs.config import GoogleDocsConfig
from crminaec.core.models import (AssessmentFormat, Course, LearningOutcome,
                                  Lesson, Tool, db)
from crminaec.web.forms import CourseForm, ImportForm, LessonForm

# ==============================================================================
# 🎓 CORE DASHBOARD & COURSE ROUTES
# ==============================================================================

@pearson_bp.route('/')
def index():
    """Home page with overview"""
    try:
        # Use the globally managed db.session!
        courses = db.session.query(Course).all()
        total_lessons = db.session.query(Lesson).count()
        
        stats = {
            'total_courses': len(courses),
            'total_lessons': total_lessons,
            'recent_courses': courses[-3:] if len(courses) > 3 else courses
        }
        
        return render_template('index.html', stats=stats, courses=courses)
    except Exception as e:
        flash(f"Database Error: {e}", "error")
        return render_template('index.html', stats={}, courses=[])

@pearson_bp.route('/courses')
def list_courses():
    """List all courses"""
    try:
        courses = db.session.query(Course).order_by(Course.created_date.desc()).all()
        return render_template('courses.html', courses=courses)
    except Exception as e:
        flash(f'Error loading courses: {str(e)}', 'error')
        return render_template('courses.html', courses=[])

@pearson_bp.route('/course/<int:course_id>')
def course_detail(course_id):
    """Show course details and lessons"""
    try:
        course = db.session.query(Course).filter_by(course_id=course_id).first()
        if not course:
            flash('Course not found', 'error')
            return redirect(url_for('pearson.list_courses'))
        
        # We can just pass the course object, as course.lessons is already sorted by the model
        lessons = course.lessons
        
        return render_template('course_detail.html', course=course, lessons=lessons)
    except Exception as e:
        flash(f'Error loading course: {str(e)}', 'error')
        return redirect(url_for('pearson.list_courses'))

@pearson_bp.route('/course/<int:course_id>/lessons')
def course_lessons(course_id):
    """Show lessons for a specific course"""
    try:
        course = db.session.query(Course).filter_by(course_id=course_id).first()
        if not course:
            flash('Course not found', 'error')
            return redirect(url_for('pearson.list_courses'))
        
        return render_template('lessons.html', course=course, lessons=course.lessons)
    except Exception as e:
        flash(f'Error loading lessons: {str(e)}', 'error')
        return redirect(url_for('pearson.list_courses'))

# ==============================================================================
# ✍️ COURSE MANAGEMENT (CREATE, EDIT, DELETE)
# ==============================================================================

@pearson_bp.route('/course/create', methods=['GET', 'POST'])
def create_course():
    """Create a new course"""
    form = CourseForm()
    if form.validate_on_submit():
        course = Course(
            course_title=form.title.data or "",
            course_code=form.course_code.data or "",
            instructor=form.instructor.data or "",
            contact_email=form.contact_email.data or "",
            level=form.level.data or "",
            language=form.language.data or "English",
            delivery_mode=form.delivery_mode.data or "",
            aim=form.aim.data or "",
            description=form.description.data or "",
            objectives=form.objectives.data or ""
        )
        db.session.add(course)
        db.session.commit()
        flash(f'Course "{course.course_title}" created successfully!', 'success')
        return redirect(url_for('pearson.course_detail', course_id=course.course_id))
    
    if request.method == 'GET':
        return render_template('course_edit.html', course=None, form=form)
    
    # POST method (Fallback if not using WTForms)
    try:
        course = Course(
            course_title=request.form['title'],
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
        
        db.session.add(course)
        db.session.commit()
        flash(f'Course "{course.course_title}" created successfully!', 'success')
        return redirect(url_for('pearson.course_detail', course_id=course.course_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating course: {str(e)}', 'error')
        return render_template('course_edit.html', form=form, course=None)

@pearson_bp.route('/course/<int:course_id>/edit', methods=['GET', 'POST'])
def edit_course(course_id):
    """Edit an existing course"""
    course = db.session.query(Course).filter_by(course_id=course_id).first()
    
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('pearson.list_courses'))
    
    if request.method == 'GET':
        return render_template('course_edit.html', course=course)
    
    try:
        course.course_title = request.form['title']
        course.course_code = request.form['course_code']
        course.instructor = request.form.get('instructor', '')
        course.contact_email = request.form.get('contact_email', '')
        course.level = request.form.get('level', '')
        course.language = request.form.get('language', 'English')
        course.delivery_mode = request.form.get('delivery_mode', '')
        course.aim = request.form.get('aim', '')
        course.description = request.form.get('description', '')
        course.objectives = request.form.get('objectives', '')
        
        db.session.commit()
        flash(f'Course "{course.course_title}" updated successfully!', 'success')
        return redirect(url_for('pearson.course_detail', course_id=course.course_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating course: {str(e)}', 'error')
        return render_template('course_edit.html', course=course)

@pearson_bp.route('/course/<int:course_id>/delete', methods=['POST'])
def delete_course(course_id):
    """Delete a course"""
    try:
        course = db.session.query(Course).filter_by(course_id=course_id).first()
        if course:
            course_title = course.course_title
            db.session.delete(course)
            db.session.commit()
            flash(f'Course "{course_title}" deleted successfully!', 'success')
        else:
            flash('Course not found', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting course: {str(e)}', 'error')
    
    return redirect(url_for('pearson.list_courses'))

# ==============================================================================
# 📖 LESSON MANAGEMENT
# ==============================================================================

@pearson_bp.route('/course/<int:course_id>/lesson/create', methods=['GET', 'POST'])
def create_lesson(course_id):
    """Create a new lesson for a course"""
    course = db.session.query(Course).filter_by(course_id=course_id).first()
    
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('pearson.list_courses'))
    
    if request.method == 'GET':
        return render_template('lesson_edit.html', course=course, lesson=None)
    
    try:
        order = int(request.form.get('order', 1))
    except ValueError:
        order = 1
        
    try:
        duration = int(request.form.get('duration', 60))
    except ValueError:
        duration = 60
        
    try:
        lesson = Lesson(
            course_id=course_id,
            lesson_title=request.form['title'],
            content=request.form.get('content', ''),
            duration=duration,
            order=order,
            activity_type=request.form.get('activity_type', ''),
            assignment_description=request.form.get('assignment_description', ''),
            materials_needed=request.form.get('materials_needed', '')
        )
        
        db.session.add(lesson)
        db.session.commit()
        flash(f'Lesson "{lesson.lesson_title}" created successfully!', 'success')
        return redirect(url_for('pearson.course_lessons', course_id=course_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating lesson: {str(e)}', 'error')
        return render_template('lesson_edit.html', course=course, lesson=None)

@pearson_bp.route('/lesson/<int:lesson_id>/edit', methods=['GET', 'POST'])
def edit_lesson(lesson_id):
    """Edit an existing lesson"""
    lesson = db.session.query(Lesson).filter_by(lesson_id=lesson_id).first()
    
    if not lesson:
        flash('Lesson not found', 'error')
        return redirect(url_for('pearson.list_courses'))
    
    course = db.session.query(Course).filter_by(course_id=lesson.course_id).first()
    
    if request.method == 'GET':
        return render_template('lesson_edit.html', course=course, lesson=lesson)
    
    try:
        try:
            lesson.order = int(request.form.get('order', lesson.order))
        except ValueError:
            pass
            
        try:
            lesson.duration = int(request.form.get('duration', lesson.duration))
        except ValueError:
            pass
            
        lesson.lesson_title = request.form['title']
        lesson.content = request.form.get('content', '')
        lesson.activity_type = request.form.get('activity_type', '')
        lesson.assignment_description = request.form.get('assignment_description', '')
        lesson.materials_needed = request.form.get('materials_needed', '')
        
        db.session.commit()
        flash(f'Lesson "{lesson.lesson_title}" updated successfully!', 'success')
        return redirect(url_for('pearson.course_lessons', course_id=lesson.course_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating lesson: {str(e)}', 'error')
        return render_template('lesson_edit.html', course=course, lesson=lesson)

@pearson_bp.route('/lesson/<int:lesson_id>/delete', methods=['POST'])
def delete_lesson(lesson_id):
    """Delete a lesson"""
    try:
        lesson = db.session.query(Lesson).filter_by(lesson_id=lesson_id).first()
        if lesson:
            course_id = lesson.course_id
            lesson_title = lesson.lesson_title
            db.session.delete(lesson)
            db.session.commit()
            flash(f'Lesson "{lesson_title}" deleted successfully!', 'success')
            return redirect(url_for('pearson.course_lessons', course_id=course_id))
        else:
            flash('Lesson not found', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting lesson: {str(e)}', 'error')
    
    return redirect(url_for('pearson.list_courses'))

# ==============================================================================
# 📥 IMPORT SYLLABUS (Markdown)
# ==============================================================================

@pearson_bp.route('/course/import', methods=['GET', 'POST'])
def import_syllabus():
    if request.method == 'GET':
        return render_template('import.html')
    
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(request.url)
    
    file = request.files['file']
    
    # 🛠️ THE PYLANCE FIX: Check for truthiness (catches both None and "")
    if not file.filename:
        flash('No file selected', 'error')
        return redirect(request.url)
    
    # Pylance now knows for an absolute fact that file.filename is a string here
    if not file.filename.endswith('.md'):
        flash('Please upload a valid Markdown (.md) file.', 'error')
        return redirect(request.url)

    temp_dir = os.path.join(current_app.instance_path, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    filename = secure_filename(file.filename)
    temp_path = os.path.join(temp_dir, filename)
    
    try:
        file.save(temp_path)
        
        # We no longer need to pass the database URL to the injector
        injector = CourseInjector()
        success = injector.inject_comprehensive_course(temp_path)
        
        if success:
            flash(f'Successfully imported course from {filename}!', 'success')
            return redirect(url_for('pearson.list_courses'))
        else:
            flash('Parsing failed. Ensure the Markdown follows the required schema.', 'error')
            return redirect(request.url)
            
    except Exception as e:
        flash(f'Import error: {str(e)}', 'error')
        return redirect(request.url)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# ==============================================================================
# ☁️ GOOGLE DOCS SYNC OPERATIONS
# ==============================================================================

@pearson_bp.route('/sync-status')
def sync_status():
    config = GoogleDocsConfig(user_id="doarch")
    client = GoogleDocsClient(config)
    
    remote_titles = set()
    auth_warning = False

    try:
        remote_docs = client.list_documents()
        remote_titles = {doc['name'] for doc in remote_docs}
    except Exception as e:
        auth_warning = True 

    specs_path = os.path.join(current_app.root_path, 'static', 'content', 'specs')
    
    sync_data = []
    if os.path.exists(specs_path):
        local_files = [f for f in os.listdir(specs_path) if f.endswith('.md')]
        for f in local_files:
            x_code = f.replace('.md', '')
            is_synced = any(x_code in title for title in remote_titles)
            sync_data.append({
                'code': x_code,
                'status': '✅ Synced' if is_synced else '☁️ Local Only',
                'filename': f
            })
    
    return render_template('sync_log.html', sync_data=sync_data, auth_warning=auth_warning)

@pearson_bp.route('/sync-all-specs', methods=['POST'])
def sync_all_specs():
    config = GoogleDocsConfig(user_id="doarch")
    client = GoogleDocsClient(config)
    
    if not client.authenticated:
        flash("❌ Authentication required. Please log in first.", "danger")
        return redirect(url_for('pearson.sync_status'))

    specs_path = os.path.join(current_app.root_path, 'static', 'content', 'specs')
    remote_docs = client.list_documents()   
    remote_titles = {doc['name'] for doc in remote_docs}
    
    sync_count = 0
    if os.path.exists(specs_path):
        for filename in os.listdir(specs_path):
            if filename.endswith('.md'):
                x_code = filename.replace('.md', '')
                
                if any(x_code in title for title in remote_titles):
                    continue
                    
                with open(os.path.join(specs_path, filename), 'r', encoding='utf-8') as f:
                    md_content = f.read()
                
                doc_id = client.create_document(title=f"AEC Spec: {x_code}")
                if doc_id:
                    client.update_content(doc_id, {'content': md_content})
                    sync_count += 1
                
    flash(f"🚀 Successfully synced {sync_count} new specifications to Google Drive!", "success")
    return redirect(url_for('pearson.sync_status'))

@pearson_bp.route('/folders')
def folder_registry():
    config = GoogleDocsConfig(user_id="kerem")
    client = GoogleDocsClient(config)
    
    folders = client.list_folders()
    default_id = config.default_folder_id
    
    return render_template('folders.html', folders=folders, default_id=default_id)