"""
Database setup and configuration for Pearson.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shared.models import Base

class DatabaseSetup:
    """Handles database setup and session management."""
    
    def __init__(self, database_url=None):
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
        self.Session = sessionmaker(bind=self.engine)
        
        # Create tables if they don't exist
        self.create_tables()
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(self.engine)
    
    def drop_tables(self):
        """Drop all database tables (for testing)."""
        Base.metadata.drop_all(self.engine)
    
    def get_session(self):
        """Get a new database session."""
        return self.Session()
    
    def reset_database(self):
        """Reset database by dropping and recreating tables."""
        self.drop_tables()
        self.create_tables()
        print(f"Database reset: {self.database_url}")