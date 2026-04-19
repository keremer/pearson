from typing import Optional
from datetime import datetime

from crminaec.core.models import Course, Order, Party, UserAccount, db
from crminaec.platforms.emek import models as emek_models


class DatabaseSetup:
    """Handles unified database setup and seed data."""
    
    def __init__(self, app):
        self.app = app

    def create_tables(self) -> None:
        """Creates all registered tables (Core + Pearson)."""
        with self.app.app_context():
            db.create_all()
            print("✅ All tables (Core & Platform) initialized.")

    def drop_tables(self) -> None:
        with self.app.app_context():
            db.drop_all()
            print("🗑️ Database wiped.")

    def create_sample_data(self) -> None:
        """Seed the database with professional roles and sample records."""
        with self.app.app_context():
            try:
                # 1. Core Users (Upgraded to Dual-Table Architecture)
                # Check existence by email now, since username is gone
                if not db.session.query(Party).filter_by(email="kerem@emek.com").first():
                    
                    # Step A: Create CRM Entities
                    kerem_party = Party(**{'email': "doarch@gmail.com", 'first_name': "Kerem"})
                    emre_party = Party(**{'email': "emerter@gmail.com", 'first_name': "Emre Mert"})
                    ediz_party = Party(**{'email': "edizer28@gmail.com", 'first_name': "Ediz"})
                    
                    db.session.add_all([kerem_party, emre_party, ediz_party])
                    db.session.commit() # Get the auto-generated party_ids safely
                    
                    # Step B: Create Security Accounts
                    accounts = [
                        UserAccount(**{'party_id': kerem_party.party_id, 'role': "admin", 'is_confirmed': True, 'kvkk_approved': True}),
                        UserAccount(**{'party_id': emre_party.party_id, 'role': "power_user", 'is_confirmed': True, 'kvkk_approved': True}),
                        UserAccount(**{'party_id': ediz_party.party_id, 'role': "instructor", 'is_confirmed': True, 'kvkk_approved': True})
                    ]
                    
                    # Set a default password for local dev testing
                    for acc in accounts:
                        acc.set_password("password123")
                        
                    db.session.add_all(accounts)

                # 2. Pearson Sample
                if not db.session.query(Course).filter_by(course_code="HND5-ID").first():
                    course = Course(**{
                        'course_title': "Interior Design Specification",
                        'course_code': "HND5-ID",
                        'level': "Level 5",
                        'created_date': datetime.now(),
                        'updated_date': datetime.now(),
                        'lessons': [],
                        'learning_outcomes': [],
                        'assessment_formats': [],
                        'tools': []
                    })
                    db.session.add(course)

                # 3. Arkhon Sample
                if not db.session.query(Order).filter_by(order_number="ORD-2026-001").first():
                    # Dynamically fetch the ID to avoid Foreign Key crashes if the DB shifted
                    kerem = db.session.query(Party).filter_by(email="kerem@emek.com").first()
                    kerem_id = kerem.party_id if kerem else None
                    
                    order = Order(**{
                        'order_number': "ORD-2026-001",
                        'party_id': kerem_id, 
                        'status': "pending"
                    })
                    db.session.add(order)

                db.session.commit()
                print("✅ Sample data injected successfully.")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error seeding data: {e}")

    def list_summary(self) -> None:
        """CLI health check."""
        with self.app.app_context():
            print(f"\n--- 🏛️ Portal Summary ---")
            print(f"👥 Users:   {db.session.query(Party).count()}")
            print(f"🔐 Accounts:{db.session.query(UserAccount).count()}")
            print(f"🎓 Courses: {db.session.query(Course).count()}")
            print(f"🏗️ Orders:  {db.session.query(Order).count()}")
            print("-" * 25)