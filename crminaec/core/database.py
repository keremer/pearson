from datetime import datetime
from typing import Optional

from crminaec.core.models import Order, Party, UserAccount, db
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
                if not db.session.scalar(db.select(Party).filter_by(email="doarch@gmail.com")):
                    
                    # Step A: Create CRM Entities
                    kerem_party = Party(**{'email': "doarch@gmail.com", 'first_name': "Kerem"})
                    emre_party = Party(**{'email': "emerter@gmail.com", 'first_name': "Emre Mert"})
                    ediz_party = Party(**{'email': "edizer28@gmail.com", 'first_name': "Ediz"})
                    
                    db.session.add_all([kerem_party, emre_party, ediz_party])
                    db.session.flush() # Get the auto-generated party_ids safely without closing the transaction
                    
                    # Step B: Create Security Accounts
                    # We MUST pass both the ID and the object to prevent the dataclass from defaulting `party` to None!
                    accounts = [
                        UserAccount(**{'party_id': kerem_party.party_id, 'party': kerem_party, 'role': "admin", 'is_confirmed': True, 'kvkk_approved': True}),
                        UserAccount(**{'party_id': emre_party.party_id, 'party': emre_party, 'role': "power_user", 'is_confirmed': True, 'kvkk_approved': True}),
                        UserAccount(**{'party_id': ediz_party.party_id, 'party': ediz_party, 'role': "instructor", 'is_confirmed': True, 'kvkk_approved': True})
                    ]
                    
                    # Set a default password for local dev testing
                    for acc in accounts:
                        acc.set_password("password123")
                        
                    db.session.add_all(accounts)

                # 2. Pearson Sample
                if not db.session.scalar(db.select(emek_models.Item).filter_by(code="HND5-ID", item_type='course')):
                    course = emek_models.Item(**{
                        'name': "Interior Design Specification",
                        'code': "HND5-ID",
                        'item_type': 'course',
                        'node_type': emek_models.NodeType.ACTIVITY,
                        'technical_specs': {'level': "Level 5"}
                    })
                    db.session.add(course)

                # 3. Arkhon Sample
                if not db.session.scalar(db.select(Order).filter_by(order_number="ORD-2026-001")):
                    # Dynamically fetch the ID to avoid Foreign Key crashes if the DB shifted
                    kerem = db.session.scalar(db.select(Party).filter_by(email="doarch@gmail.com"))
                    kerem_id = kerem.party_id if kerem else None
                    
                    order = Order(**{
                        'order_number': "ORD-2026-001",
                        'party_id': kerem_id,
                        'party': kerem, # Pass the object here as well!
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
            print(f"👥 Users:   {db.session.scalar(db.select(db.func.count(Party.party_id)))}")
            print(f"🔐 Accounts:{db.session.scalar(db.select(db.func.count(UserAccount.account_id)))}")
            print(f"🎓 Courses: {db.session.scalar(db.select(db.func.count(emek_models.Item.item_id)).filter_by(item_type='course'))}")
            print(f"🏗️ Orders:  {db.session.scalar(db.select(db.func.count(Order.order_id)))}")
            print("-" * 25)