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
# Fix Imports for new architecture
from crminaec.cli.course_injector import CourseInjector
# Google Interop Imports
from crminaec.core.interop.google_docs.client import GoogleDocsClient
from crminaec.core.interop.google_docs.config import GoogleDocsConfig
from crminaec.core.models import db
from crminaec.platforms.emek.models import Item, ItemComposition, NodeType
from crminaec.web.forms import CourseForm, ImportForm, LessonForm

pearson_bp = Blueprint('pearson', __name__)

# ==============================================================================
# 🎓 CORE DASHBOARD & COURSE ROUTES
# ==============================================================================

@pearson_bp.route('/')
def index():
    """Home page with overview"""
    try:
        # Query Universal Items instead
        courses = db.session.query(Item).filter_by(item_type='course').all()
        total_lessons = db.session.query(Item).filter_by(item_type='lesson').count()
        
        stats = {
            'total_courses': len(courses),
            'total_lessons': total_lessons,
            'recent_courses': courses[-3:] if len(courses) > 3 else courses
        }
        
        return render_template('pearson/index.html', stats=stats, courses=courses)
    except Exception as e:
        flash(f"Database Error: {e}", "error")
        return render_template('pearson/index.html', stats={}, courses=[])

@pearson_bp.route('/courses')
def list_courses():
    """List all courses"""
    try:
        courses = db.session.query(Item).filter_by(item_type='course').all()
        return render_template('pearson/courses.html', courses=courses)
    except Exception as e:
        flash(f'Error loading courses: {str(e)}', 'error')
        return render_template('pearson/courses.html', courses=[])

@pearson_bp.route('/course/<int:course_id>')
def course_detail(course_id):
    """Show course details and lessons"""
    try:
        course = db.session.query(Item).filter_by(item_id=course_id, item_type='course').first()
        if not course:
            flash('Course not found', 'error')
            return redirect(url_for('pearson.list_courses'))
        
        # Query BOM links for lessons
        comps = db.session.query(ItemComposition).filter_by(parent_id=course_id).order_by(ItemComposition.sort_order).all()
        lessons = [c.child_item for c in comps if c.child_item.item_type == 'lesson']
        
        return render_template('pearson/course_detail.html', course=course, lessons=lessons)
    except Exception as e:
        flash(f'Error loading course: {str(e)}', 'error')
        return redirect(url_for('pearson.list_courses'))

@pearson_bp.route('/course/<int:course_id>/lessons')
def course_lessons(course_id):
    """Show lessons for a specific course"""
    try:
        course = db.session.query(Item).filter_by(item_id=course_id, item_type='course').first()
        if not course:
            flash('Course not found', 'error')
            return redirect(url_for('pearson.list_courses'))
        
        comps = db.session.query(ItemComposition).filter_by(parent_id=course_id).order_by(ItemComposition.sort_order).all()
        lessons = [c.child_item for c in comps if c.child_item.item_type == 'lesson']
        
        return render_template('pearson/lessons.html', course=course, lessons=lessons)
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
        tech_specs = {
            'instructor': form.instructor.data or "",
            'contact_email': form.contact_email.data or "",
            'level': form.level.data or "",
            'language': form.language.data or "English",
            'delivery_mode': form.delivery_mode.data or "",
            'aim': form.aim.data or "",
            'description': form.description.data or "",
            'objectives': form.objectives.data or ""
        }
        course = Item(
            name=form.title.data or "",
            code=form.course_code.data or "",
            item_type='course',
            node_type=NodeType.ACTIVITY,
            technical_specs=tech_specs
        )
        db.session.add(course)
        db.session.commit()
        flash(f'Course "{course.name}" created successfully!', 'success')
        return redirect(url_for('pearson.course_detail', course_id=course.item_id))
    
    if request.method == 'GET':
        return render_template('pearson/course_edit.html', course=None, form=form)
    
    # POST method (Fallback if not using WTForms)
    try:
        tech_specs = {
            'instructor': request.form.get('instructor', ''),
            'contact_email': request.form.get('contact_email', ''),
            'level': request.form.get('level', ''),
            'language': request.form.get('language', 'English'),
            'delivery_mode': request.form.get('delivery_mode', ''),
            'aim': request.form.get('aim', ''),
            'description': request.form.get('description', ''),
            'objectives': request.form.get('objectives', '')
        }
        course = Item(
            name=request.form['title'],
            code=request.form['course_code'],
            item_type='course',
            node_type=NodeType.ACTIVITY,
            technical_specs=tech_specs
        )
        
        db.session.add(course)
        db.session.commit()
        flash(f'Course "{course.name}" created successfully!', 'success')
        return redirect(url_for('pearson.course_detail', course_id=course.item_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating course: {str(e)}', 'error')
        return render_template('pearson/course_edit.html', form=form, course=None)

@pearson_bp.route('/course/<int:course_id>/edit', methods=['GET', 'POST'])
def edit_course(course_id):
    """Edit an existing course"""
    course = db.session.query(Item).filter_by(item_id=course_id, item_type='course').first()
    
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('pearson.list_courses'))
    
    if request.method == 'GET':
        return render_template('pearson/course_edit.html', course=course)
    
    try:
        course.name = request.form['title']
        course.code = request.form['course_code']
        
        if not course.technical_specs: course.technical_specs = {}
        course.technical_specs['instructor'] = request.form.get('instructor', '')
        course.technical_specs['contact_email'] = request.form.get('contact_email', '')
        course.technical_specs['level'] = request.form.get('level', '')
        course.technical_specs['language'] = request.form.get('language', 'English')
        course.technical_specs['delivery_mode'] = request.form.get('delivery_mode', '')
        course.technical_specs['aim'] = request.form.get('aim', '')
        course.technical_specs['description'] = request.form.get('description', '')
        course.technical_specs['objectives'] = request.form.get('objectives', '')
        
        db.session.commit()
        flash(f'Course "{course.name}" updated successfully!', 'success')
        return redirect(url_for('pearson.course_detail', course_id=course.item_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating course: {str(e)}', 'error')
        return render_template('pearson/course_edit.html', course=course)

@pearson_bp.route('/course/<int:course_id>/delete', methods=['POST'])
def delete_course(course_id):
    """Delete a course"""
    try:
        course = db.session.query(Item).filter_by(item_id=course_id, item_type='course').first()
        if course:
            course_title = course.name
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
    course = db.session.query(Item).filter_by(item_id=course_id, item_type='course').first()
    
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('pearson.list_courses'))
    
    if request.method == 'GET':
        return render_template('pearson/lesson_edit.html', course=course, lesson=None)
    
    try:
        order = int(request.form.get('order', 1))
    except ValueError:
        order = 1
        
    try:
        duration = int(request.form.get('duration', 60))
    except ValueError:
        duration = 60
        
    try:
        tech_specs = {
            'duration': duration,
            'activity_type': request.form.get('activity_type', ''),
            'assignment_description': request.form.get('assignment_description', ''),
            'materials_needed': request.form.get('materials_needed', '')
        }
        
        lesson = Item(
            name=request.form['title'],
            code=f"LESSON-{order}",
            item_type='lesson',
            node_type=NodeType.ACTIVITY,
            technical_specs=tech_specs
        )
        
        db.session.add(lesson)
        db.session.flush()
        
        # Link lesson to course via BOM composition
        comp = ItemComposition(parent_item=course, child_item=lesson, sort_order=order, optional_attributes={})
        db.session.add(comp)
        
        db.session.commit()
        flash(f'Lesson "{lesson.name}" created successfully!', 'success')
        return redirect(url_for('pearson.course_lessons', course_id=course_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating lesson: {str(e)}', 'error')
        return render_template('pearson/lesson_edit.html', course=course, lesson=None)

@pearson_bp.route('/lesson/<int:lesson_id>/edit', methods=['GET', 'POST'])
def edit_lesson(lesson_id):
    """Edit an existing lesson"""
    lesson = db.session.query(Item).filter_by(item_id=lesson_id, item_type='lesson').first()
    
    if not lesson:
        flash('Lesson not found', 'error')
        return redirect(url_for('pearson.list_courses'))
        
    # Find parent course
    comp = db.session.query(ItemComposition).filter_by(child_id=lesson_id).first()
    course = comp.parent_item if comp else None
    
    if request.method == 'GET':
        return render_template('pearson/lesson_edit.html', course=course, lesson=lesson)
    
    try:
        try:
            if comp:
                comp.sort_order = int(request.form.get('order', comp.sort_order))
        except ValueError:
            pass
            
        lesson.name = request.form['title']
        
        if not lesson.technical_specs: lesson.technical_specs = {}
        try:
            lesson.technical_specs['duration'] = int(request.form.get('duration', lesson.technical_specs.get('duration', 60)))
        except ValueError:
            pass
        lesson.technical_specs['activity_type'] = request.form.get('activity_type', '')
        lesson.technical_specs['assignment_description'] = request.form.get('assignment_description', '')
        lesson.technical_specs['materials_needed'] = request.form.get('materials_needed', '')
        
        db.session.commit()
        flash(f'Lesson "{lesson.name}" updated successfully!', 'success')
        return redirect(url_for('pearson.course_lessons', course_id=course.item_id if course else 0))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating lesson: {str(e)}', 'error')
        return render_template('pearson/lesson_edit.html', course=course, lesson=lesson)

@pearson_bp.route('/lesson/<int:lesson_id>/delete', methods=['POST'])
def delete_lesson(lesson_id):
    """Delete a lesson"""
    try:
        lesson = db.session.query(Item).filter_by(item_id=lesson_id, item_type='lesson').first()
        if lesson:
            comp = db.session.query(ItemComposition).filter_by(child_id=lesson_id).first()
            course_id = comp.parent_id if comp else 0
            lesson_title = lesson.name
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
        return render_template('pearson/import.html')
    
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
    
    return render_template('pearson/sync_log.html', sync_data=sync_data, auth_warning=auth_warning)

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
    
    return render_template('pearson/folders.html', folders=folders, default_id=default_id)