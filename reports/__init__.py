# pearson/reports/__init__.py
"""
Reporting module for Pearson Course Management System.
Provides template management and multi-format export capabilities.
"""
from .template_manager import TemplateManager, CourseDataBuilder
from .multi_exporter import MultiExporter

__all__ = ['TemplateManager', 'CourseDataBuilder', 'MultiExporter']