#!/usr/bin/env python3
"""
CLI Argument Parser Setup for Course Automation System
Updated for new project structure
"""

import argparse
import sys
from pathlib import Path

def setup_argparse():
    """Setup the main argument parser"""
    parser = argparse.ArgumentParser(
        description="Course Automation System - Generate course materials automatically",
        epilog="Example: python run_cli.py generate --course-id 1 --format markdown"
    )
    
    # Global arguments
    parser.add_argument(
        '--database', 
        default='sqlite:///courses.db',
        help='Database URL (default: sqlite:///courses.db)'
    )
    parser.add_argument(
        '--output-dir', 
        default='output',
        help='Output directory (default: output)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(
        dest='command',
        title='commands',
        description='Available commands',
        help='Additional help with <command> -h',
        required=True  # Make command required
    )
    
    # Generate command
    generate_parser = subparsers.add_parser(
        'generate', 
        help='Generate course materials'
    )
    _setup_generate_parser(generate_parser)
    
    # List command
    list_parser = subparsers.add_parser(
        'list', 
        help='List courses and lessons'
    )
    _setup_list_parser(list_parser)
    
    # Add command
    add_parser = subparsers.add_parser(
        'add', 
        help='Add new course or lesson'
    )
    _setup_add_parser(add_parser)
    
    # Export command
    export_parser = subparsers.add_parser(
        'export', 
        help='Export course data'
    )
    _setup_export_parser(export_parser)
    
    # Batch command
    batch_parser = subparsers.add_parser(
        'batch', 
        help='Batch process all courses'
    )
    _setup_batch_parser(batch_parser)
    
    # Setup command (NEW)
    setup_parser = subparsers.add_parser(
        'setup',
        help='Setup database and create sample data'
    )
    _setup_setup_parser(setup_parser)
    
    # Inject command (NEW)
    inject_parser = subparsers.add_parser(
        'inject',
        help='Inject course from markdown syllabus'
    )
    _setup_inject_parser(inject_parser)
    
    return parser

def _setup_generate_parser(parser):
    """Setup arguments for generate command"""
    parser.add_argument(
        '--course-id', '-c',
        type=int,
        help='Course ID to generate materials for'
    )
    parser.add_argument(
        '--lesson-id', '-l',
        type=int,
        help='Specific lesson ID to generate (requires --course-id)'
    )
    parser.add_argument(
        '--format', '-f',
        nargs='+',
        choices=['pdf', 'html', 'markdown', 'all'],
        default=['markdown'],
        help='Output formats (default: markdown)'
    )
    parser.add_argument(
        '--template', '-t',
        choices=['syllabus', 'lesson', 'overview', 'all'],
        default=['all'],
        nargs='+',
        help='Templates to generate (default: all)'
    )
    parser.add_argument(
        '--batch', '-b',
        action='store_true',
        help='Generate for all courses'
    )

def _setup_list_parser(parser):
    """Setup arguments for list command"""
    parser.add_argument(
        'what',
        choices=['courses', 'lessons', 'all'],
        default='courses',
        nargs='?',
        help='What to list (default: courses)'
    )
    parser.add_argument(
        '--course-id', '-c',
        type=int,
        help='Filter lessons by course ID'
    )
    parser.add_argument(
        '--detailed', '-d',
        action='store_true',
        help='Show detailed information'
    )

def _setup_add_parser(parser):
    """Setup arguments for add command"""
    parser.add_argument(
        'what',
        choices=['course', 'lesson'],
        help='What to add (course or lesson)'
    )
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Interactive mode (prompt for details)'
    )
    parser.add_argument(
        '--file', '-f',
        help='JSON file with course/lesson data'
    )
    parser.add_argument(
        '--course-id', '-c',
        type=int,
        help='Course ID for adding a lesson'
    )

def _setup_export_parser(parser):
    """Setup arguments for export command"""
    parser.add_argument(
        '--course-id', '-c',
        type=int,
        required=True,
        help='Course ID to export'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'yaml', 'csv'],
        default='json',
        help='Export format (default: json)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file (default: auto-generated)'
    )

def _setup_batch_parser(parser):
    """Setup arguments for batch command"""
    parser.add_argument(
        '--format', '-f',
        nargs='+',
        choices=['pdf', 'html', 'markdown', 'all'],
        default=['all'],
        help='Output formats (default: all)'
    )
    parser.add_argument(
        '--template', '-t',
        choices=['syllabus', 'lesson', 'overview', 'all'],
        default=['all'],
        nargs='+',
        help='Templates to generate (default: all)'
    )
    parser.add_argument(
        '--parallel', '-p',
        action='store_true',
        help='Process courses in parallel (experimental)'
    )

def _setup_setup_parser(parser):
    """Setup arguments for setup command"""
    parser.add_argument(
        '--reset', '-r',
        action='store_true',
        help='Reset database (drop and recreate)'
    )
    parser.add_argument(
        '--sample-data', '-s',
        action='store_true',
        help='Create sample course data'
    )

def _setup_inject_parser(parser):
    """Setup arguments for inject command"""
    parser.add_argument(
        'file',
        help='Markdown syllabus file to inject'
    )
    parser.add_argument(
        '--database', '-d',
        help='Custom database URL'
    )

def main():
    """Test the argument parser"""
    parser = setup_argparse()
    args = parser.parse_args(['--help'])
    
    if args.command:
        print(f"Command: {args.command}")
        print(f"Args: {vars(args)}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()