"""
Functional tests for web routes.
"""
import pytest
import io
from flask import url_for
import pearson.tests.conftest as conftest
import pearson.shared.models as models

class TestIndexRoute:
    """Tests for the index route."""
    
    def test_index_route(self, client):
        """Test that index route returns successfully."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Course Management' in response.data
    
    def test_index_with_courses(self, client, db_session):
        """Test index route with existing courses."""
        # Create test courses
        course1 = conftest.create_test_course(db_session, title='Course 1')
        course2 = conftest.create_test_course(db_session, title='Course 2')
        
        response = client.get('/')
        assert response.status_code == 200
        assert b'Course 1' in response.data
        assert b'Course 2' in response.data

class TestCourseRoutes:
    """Tests for course-related routes."""
    
    def test_list_courses_empty(self, client):
        """Test courses list when no courses exist."""
        response = client.get('/courses')
        assert response.status_code == 200
        assert b'No courses found' in response.data
    
    def test_list_courses_with_data(self, client, db_session):
        """Test courses list with existing courses."""
        conftest.create_test_course(db_session, title='Python Course')
        
        response = client.get('/courses')
        assert response.status_code == 200
        assert b'Python Course' in response.data
    
    def test_course_detail_success(self, client, db_session):
        """Test viewing course details."""
        course = conftest.create_test_course(db_session, title='Test Course')
        
        response = client.get(f'/course/{course.id}')
        assert response.status_code == 200
        assert b'Test Course' in response.data
    
    def test_course_detail_not_found(self, client):
        """Test viewing non-existent course."""
        response = client.get('/course/999')
        assert response.status_code == 302  # Should redirect
        # Follow redirect
        response = client.get('/course/999', follow_redirects=True)
        assert b'Course not found' in response.data
    
    def test_create_course_get(self, client):
        """Test GET request to create course form."""
        response = client.get('/course/create')
        assert response.status_code == 200
        assert b'Create New Course' in response.data
    
    def test_create_course_post(self, client, db_session):
        """Test POST request to create a course."""
        data = {
            'title': 'New Course',
            'course_code': 'NC101',
            'instructor': 'Test Instructor',
            'level': 'Intermediate',
            'language': 'English',
            'delivery_mode': 'Hybrid'
        }
        
        response = client.post('/course/create', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b'New Course' in response.data
        assert b'created successfully' in response.data
        
        # Verify course was created in database
        courses = db_session.query(models.Course).filter_by(title='New Course').all()
        assert len(courses) == 1
    
    def test_edit_course(self, client, db_session):
        """Test editing an existing course."""
        course = conftest.create_test_course(db_session, title='Original Title')
        
        # GET edit form
        response = client.get(f'/course/{course.id}/edit')
        assert response.status_code == 200
        assert b'Original Title' in response.data
        
        # POST updated data
        data = {
            'title': 'Updated Title',
            'course_code': course.course_code,
            'instructor': 'Updated Instructor'
        }
        
        response = client.post(f'/course/{course.id}/edit', 
                              data=data, 
                              follow_redirects=True)
        assert response.status_code == 200
        assert b'Updated Title' in response.data
        assert b'updated successfully' in response.data
        
        # Verify update in database
        updated_course = db_session.query(models.Course).get(course.id)
        assert updated_course.title == 'Updated Title'

class TestLessonRoutes:
    """Tests for lesson-related routes."""
    
    def test_create_lesson(self, client, db_session):
        """Test creating a new lesson."""
        course = conftest.create_test_course(db_session)
        
        data = {
            'title': 'New Lesson',
            'content': 'Lesson content',
            'duration': '45',
            'order': '1',
            'activity_type': 'Workshop'
        }
        
        response = client.post(f'/course/{course.id}/lesson/create', 
                              data=data, 
                              follow_redirects=True)
        assert response.status_code == 200
        assert b'New Lesson' in response.data
        assert b'created successfully' in response.data
    
    def test_delete_lesson(self, client, db_session):
        """Test deleting a lesson."""
        course = conftest.create_test_course(db_session)
        lesson = conftest.create_test_lesson(db_session, course.id, title='Lesson to Delete')
        
        response = client.post(f'/lesson/{lesson.id}/delete', 
                              follow_redirects=True)
        assert response.status_code == 200
        assert b'deleted successfully' in response.data
        
        # Verify deletion
        deleted_lesson = db_session.query(models.Lesson).get(lesson.id)
        assert deleted_lesson is None

class TestImportRoute:
    """Tests for syllabus import route."""
    
    def test_import_page_get(self, client):
        """Test GET request to import page."""
        response = client.get('/course/import')
        assert response.status_code == 200
        assert b'Import Syllabus' in response.data
    
    def test_import_no_file(self, client):
        """Test import with no file uploaded."""
        response = client.post('/course/import', 
                              data={}, 
                              follow_redirects=True)
        assert response.status_code == 200
        assert b'No file part' in response.data
    
    def test_import_invalid_file_type(self, client):
        """Test import with invalid file type."""
        data = {
            'file': (io.BytesIO(b'test content'), 'test.txt')
        }
        
        response = client.post('/course/import', 
                              data=data, 
                              content_type='multipart/form-data',
                              follow_redirects=True)
        assert b'Please upload a valid Markdown' in response.data
    
    @pytest.mark.skip(reason="Requires actual CourseInjector implementation")
    def test_import_success(self, client, mock_course_injector, tmp_path):
        """Test successful syllabus import."""
        # Mock the injector
        mock_injector_instance = mock_course_injector.return_value
        mock_injector_instance.inject_comprehensive_course.return_value = True
        
        # Create a mock markdown file
        md_content = b"# Test Course\n\n## Course Code: TC101"
        data = {
            'file': (io.BytesIO(md_content), 'test.md')
        }
        
        response = client.post('/course/import', 
                              data=data, 
                              content_type='multipart/form-data',
                              follow_redirects=True)
        
        # Should redirect to courses list
        assert response.status_code == 200
        assert b'Successfully imported' in response.data