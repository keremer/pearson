"""
Database setup and configuration for Pearson.
"""
import os
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
from pearson.models import Base, Course, Lesson


class DatabaseSetup:
    """Handles database setup and session management."""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database setup.
        
        Args:
            database_url (str): SQLAlchemy database URL.
                If None, uses default SQLite in data folder.
        """
        if database_url is None:
            # Use default data folder
            from pearson import get_database_url
            database_url = get_database_url()
        
        self.database_url = database_url
        self.engine = create_engine(database_url, echo=False)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
        # Create data directory if it doesn't exist
        if database_url.startswith('sqlite:///'):
            db_path = database_url.replace('sqlite:///', '')
            if not db_path.startswith('/'):  # Relative path
                db_path = Path(db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def create_tables(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(self.engine)
        print(f"✅ Created database tables at: {self.database_url}")
    
    def drop_tables(self) -> None:
        """Drop all database tables (for testing)."""
        Base.metadata.drop_all(self.engine)
        print(f"🗑️  Dropped all database tables")
    
    def get_session(self):
        """Get a new database session."""
        return self.Session()
    
    def reset_database(self) -> None:
        """Reset database by dropping and recreating tables."""
        self.drop_tables()
        self.create_tables()
        print(f"🔄 Database reset: {self.database_url}")
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        inspector = inspect(self.engine)
        return table_name in inspector.get_table_names()
    
    def get_table_info(self, table_name: str) -> Optional[dict]:
        """Get information about a specific table."""
        inspector = inspect(self.engine)
        if table_name not in inspector.get_table_names():
            return None
        
        columns = inspector.get_columns(table_name)
        indexes = inspector.get_indexes(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        
        return {
            'columns': columns,
            'indexes': indexes,
            'foreign_keys': foreign_keys,
            'row_count': self._get_row_count(table_name)
        }
    
    def _get_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        try:
            session = self.get_session()
            # Use SQLAlchemy text() construct for raw SQL
            result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
            session.close()
            return count if count is not None else 0
        except Exception as e:
            print(f"⚠️  Error getting row count for {table_name}: {e}")
            return 0
    
    def list_tables(self) -> list:
        """List all tables in the database."""
        inspector = inspect(self.engine)
        return inspector.get_table_names()
    
    def create_database(self) -> None:
        """Alias for create_tables for backward compatibility."""
        self.create_tables()
    
    def drop_database(self) -> None:
        """Alias for drop_tables for backward compatibility."""
        self.drop_tables()
    
    def create_sample_data(self) -> None:
        """Create sample course data."""
        session = self.get_session()
        try:
            # Create a sample course
            course = Course(
                title="Introduction to Python Programming",
                course_code="PY101",
                instructor="Dr. Python Expert",
                contact_email="python@example.com",
                level="Beginner",
                language="English",
                delivery_mode="Online",
                aim="Teach basic Python programming concepts",
                description="A comprehensive introduction to Python programming",
                objectives="Understand variables, control structures, functions"
            )
            
            session.add(course)
            session.flush()  # Get the course ID
            
            print(f"✅ Created sample course: {course.title}")
            
            # Create sample lessons
            lesson1 = Lesson(
                course_id=course.id,
                title="Introduction to Python",
                content="Basic syntax, variables, and data types",
                duration=90,
                order=1,
                activity_type="Lecture",
                assignment_description="Write a simple Python program"
            )
            
            lesson2 = Lesson(
                course_id=course.id,
                title="Control Structures",
                content="If statements, loops, and functions",
                duration=120,
                order=2,
                activity_type="Workshop",
                assignment_description="Create a program with control structures"
            )
            
            session.add_all([lesson1, lesson2])
            session.commit()
            
            print("✅ Created sample lessons")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error creating sample data: {e}")
        finally:
            session.close()
    
    def list_courses(self) -> None:
        """List all courses in the database."""
        session = self.get_session()
        try:
            courses = session.query(Course).all()
            
            if not courses:
                print("📭 No courses found in the database.")
                return
            
            print(f"\n📚 Courses in database ({len(courses)}):")
            print("=" * 60)
            
            for course in courses:
                lesson_count = session.query(Lesson).filter_by(course_id=course.id).count()
                print(f"ID: {course.id:3d} | {course.course_code:10} | {course.title}")
                print(f"     Instructor: {course.instructor or 'Not specified'}")
                print(f"     Lessons: {lesson_count} | Level: {course.level or 'Not specified'}")
                print()
                
        except Exception as e:
            print(f"❌ Error listing courses: {e}")
        finally:
            session.close()