from typing import Optional

from crminaec.core.models import Course, Order, Party, db

# Import Pearson models from their specific location

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
                # 1. Core Users
                if not Party.query.filter_by(username="kerem").first():
                    parties = [
                        Party(username="kerem", email="kerem@emek.com", role="admin"),
                        Party(username="emre", email="emre@emek.com", role="architect"),
                        Party(username="mert", email="mert@academic.com", role="instructor")
                    ]
                    db.session.add_all(parties)

                # 2. Pearson Sample
                if not Course.query.filter_by(course_code="HND5-ID").first():
                    course = Course(
                        course_title="Interior Design Specification",
                        course_code="HND5-ID",
                        level="Level 5"
                    )
                    db.session.add(course)

                # 3. Arkhon Sample
                order = Order(
                    order_number="ORD-2026-001",
                    party_id=1,  # Assuming a default party ID
                    status="pending"
                )
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
            print(f"👥 Users:   {Party.query.count()}")
            print(f"🎓 Courses: {Course.query.count()}")
            print(f"🏗️ Orders:  {Order.query.count()}")
            print("-" * 25)