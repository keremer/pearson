from flask import jsonify

from crminaec.core.models import Course, db


def init_course_routes(app):
    
    @app.route('/api/courses', methods=['GET'])
    def get_courses():
        """Get all courses (Summary View)"""
        try:
            # SQLAlchemy 2.0 query style
            courses = db.session.execute(db.select(Course)).scalars().all()
            
            # We use the built-in to_dict() method! 
            # include_relationships=False keeps the list lightweight
            return jsonify([course.to_dict(include_relationships=False) for course in courses])
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    @app.route('/api/courses/<int:course_id>', methods=['GET'])
    def get_course(course_id):
        """Get single course by ID (Detailed View)"""
        try:
            # db.session.get() is the modern SQLAlchemy 2.0 way to fetch by Primary Key
            course = db.session.get(Course, course_id)
            
            if course:
                # include_relationships=True so the API returns the Lessons, Outcomes, etc.
                return jsonify(course.to_dict(include_relationships=True))
            
            return jsonify({'error': 'Course not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500