"""
CLI module for crminaec Platform.
Integrated with Flask-SQLAlchemy Data-First Architecture.
"""
from .commands import CLICommands
from .course_injector import CourseInjector

__all__ = ['CLICommands', 'CourseInjector']
