#!/usr/bin/env python3
"""
Day 1 Complete Setup and Test Script
Runs database setup and PDF generation tests
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent  # Goes from tests/ to pearson_app/
sys.path.insert(0, str(project_root))

def main():
    print("🎯 COURSE AUTOMATION SYSTEM - DAY 1")
    print("=" * 60)
    
    # Step 1: Database Setup
    print("\n📦 STEP 1: Database Setup")
    print("-" * 30)
    
    from app.cli.setup import main as db_main
    try:
        db_main()
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return
    
    # Step 2: PDF Generation Test
    print("\n📄 STEP 2: PDF Generation Test")
    print("-" * 30)
    
    from app.reports.pdf_generator import main as pdf_main
    try:
        pdf_main()
    except Exception as e:
        print(f"❌ PDF generation test failed: {e}")
        return
    
    # Step 3: Verification
    print("\n✅ STEP 3: Verification")
    print("-" * 30)
    
    # Check if files were created
    output_files = list(Path("output").glob("*.pdf"))
    if output_files:
        print("Generated PDF files:")
        for pdf_file in output_files:
            print(f"   📄 {pdf_file.name} ({pdf_file.stat().st_size} bytes)")
    else:
        print("❌ No PDF files were generated!")
        return
    
    # Database verification
    from app.cli.setup import DatabaseSetup
    db_setup = DatabaseSetup()
    db_setup.list_courses()
    
    print("\n🎉 DAY 1 COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\nNext steps for Day 2:")
    print("• Create Jinja2 templates for course materials")
    print("• Build template management system")
    print("• Generate Markdown and HTML outputs")

if __name__ == "__main__":
    main()