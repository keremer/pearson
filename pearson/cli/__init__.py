"""
CLI module for Pearson Course Management System.
"""
from .commands import CLICommands
from .setup import DatabaseSetup
from .course_injector import CourseInjector
from .argparse_setup import setup_argparse

__all__ = ['CLICommands', 'DatabaseSetup', 'CourseInjector', 'setup_argparse']