from crminaec.core.models import db
from crminaec.platforms.emek.models import Item, ItemComposition


def inject_project_structure():
    """Builds the master hierarchy for the organization."""
    
    # Safety Helper to instantly generate and link folders
    def create_node(code: str, name: str, parent: Item = None) -> Item:
        folder = db.session.query(Item).filter_by(code=code).first()
        if not folder:
            folder = Item(code=code, name=name, is_category=True, base_cost=0.0)
            db.session.add(folder)
            db.session.flush()
        
        if parent:
            link = db.session.query(ItemComposition).filter_by(
                parent_id=parent.item_id, child_id=folder.item_id
            ).first()
            if not link:
                db.session.add(ItemComposition(parent_item=parent, child_item=folder, quantity=1.0))
                db.session.flush()
                
        return folder

    print("🌱 Starting structural injection...")

    # ==========================================
    # 1. THE MASTER ROOT
    # ==========================================
    emek_root = create_node("EMEK", "EMEK Architecture")

    # ==========================================
    # 2. MAIN DIVISIONS
    # ==========================================
    prj_dir = create_node("DIR-PRJ", "Projects & Installations", emek_root)
    edu_dir = create_node("DIR-EDU", "Academic & Curriculum", emek_root)
    rnd_dir = create_node("DIR-RND", "Research & Development", emek_root)
    lib_dir = create_node("DIR-LIB", "Libraries & Archives", emek_root)

    # ==========================================
    # 3. SPECIFIC WORKSPACES & INITIATIVES
    # ==========================================
    
    # --- R&D ---
    create_node("RND-CRM", "crminaec Framework", rnd_dir)
    create_node("RND-BAU", "Bauhaus Pedagogical Studies", rnd_dir)

    # --- Academic ---
    create_node("EDU-HND5", "Pearson HND5 Art & Design", edu_dir)
    create_node("EDU-CAS", "Course Automation System", edu_dir)

    # --- Libraries ---
    create_node("LIB-NOTES", "ArchNotes Repository", lib_dir)

    # --- Installations ---
    create_node("PRJ-INST01", "Mirror Star Prism Installation", prj_dir)

    # Lock it in!
    db.session.commit()
    print("✅ Organizational structure successfully injected into the database!")

if __name__ == "__main__":
    from crminaec import \
        create_app  # Adjust this import based on your app factory
    app = create_app()
    with app.app_context():
        inject_project_structure()