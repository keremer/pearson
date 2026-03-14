"""
Tests for API endpoints.
"""
import pytest
import json
import pearson.tests.conftest

class TestAPIRoutes:
    """Tests for JSON API endpoints."""
    
    def test_api_courses_empty(self, client):
        """Test API courses endpoint with no courses."""
        response = client.get('/api/courses')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_api_courses_with_data(self, client, db_session):
        """Test API courses endpoint with courses."""
        pearson.tests.conftest.create_test_course(db_session, title='API Course 1')
        pearson.tests.conftest.create_test_course(db_session, title='API Course 2')
        
        response = client.get('/api/courses')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == 2
        assert data[0]['title'] == 'API Course 1'
        assert 'id' in data[0]
        assert 'code' in data[0]
        assert 'lesson_count' in data[0]
    
    def test_api_course_lessons(self, client, db_session):
        """Test API course lessons endpoint."""
        course = pearson.tests.conftest.create_test_course(db_session)
        pearson.tests.conftest.create_test_lesson(db_session, course.id, title='Lesson 1', order=1)
        pearson.tests.conftest.create_test_lesson(db_session, course.id, title='Lesson 2', order=2)
        
        response = client.get(f'/api/course/{course.id}/lessons')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == 2
        assert data[0]['title'] == 'Lesson 1'
        assert data[0]['order'] == 1
        assert data[1]['title'] == 'Lesson 2'
        assert data[1]['order'] == 2
    
    def test_api_course_lessons_not_found(self, client):
        """Test API lessons for non-existent course."""
        response = client.get('/api/course/999/lessons')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_api_error_handling(self, client, mocker):
        """Test API error handling."""
        # Mock database error
        mocker.patch('web.routes.get_db_session', side_effect=Exception('DB Error'))
        
        response = client.get('/api/courses')
        assert response.status_code == 500
        
        data = json.loads(response.data)
        assert 'error' in data