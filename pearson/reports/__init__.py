# pearson/reports/__init__.py
"""
Reporting module for Pearson Course Management System.
Provides template management and multi-format export capabilities.
"""
from pearson.reports.template_manager import TemplateManager, CourseDataBuilder
from pearson.reports.multi_exporter import MultiExporter

__all__ = ['TemplateManager', 'CourseDataBuilder', 'MultiExporter']