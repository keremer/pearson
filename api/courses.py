from flask import jsonify, request
from shared.models import Course
from cli.setup import DatabaseSetup

def init_course_routes(app):
    db_setup = DatabaseSetup()
    
    @app.route('/api/courses', methods=['GET'])
    def get_courses():
        """Get all courses"""
        session = db_setup.Session()
        try:
            courses = session.query(Course).all()
            return jsonify([serialize_course(course) for course in courses])
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    
    @app.route('/api/courses/<int:course_id>', methods=['GET'])
    def get_course(course_id):
        """Get single course by ID"""
        session = db_setup.Session()
        try:
            course = session.query(Course).filter(Course.id == course_id).first()
            if course:
                return jsonify(serialize_course(course))
            return jsonify({'error': 'Course not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

def serialize_course(course):
    """Convert Course object to JSON-serializable dict"""
    return {
        'id': course.id,
        'title': course.title,
        'course_code': course.course_code,
        'instructor': course.instructor,
        'level': course.level,
        'language': course.language,
        'delivery_mode': course.delivery_mode,
        'aim': course.aim,
        'description': course.description,
        'lesson_count': len(course.lessons) if course.lessons else 0,
        'created_date': course.created_date.isoformat() if course.created_date else None
    }