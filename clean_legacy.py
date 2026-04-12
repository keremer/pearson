import re

import click

from crminaec.core.database import db
from crminaec.platforms.emek.models import Item, ItemComposition, PriceSource


def run_cleanup(app):
    with app.app_context():
        print("🧹 Semantic Cleansing Started...")
        
        # ==========================================
        # TASK 2: Deduplicate Names (The "Kapak" Problem)
        # ==========================================
        print("🔍 Adım 1: İsim Kopyalarını Ebeveyn/Varyant Grubuna Dönüştürme...")
        
        # Find all names that have more than 1 item associated with them
        duplicate_names = db.session.execute(
            db.text("SELECT name, COUNT(*) as cnt FROM emek_items GROUP BY name HAVING cnt > 1")
        ).fetchall()

        for row in duplicate_names:
            master_name = row[0]
            # Exclude empty names or generic numbers
            if not master_name or len(master_name) < 3: 
                continue

            print(f"  -> '{master_name}' için Master Grup oluşturuluyor...")
            
            # Create the Global Master Item (e.g., KAPAK_MASTER)
            master_code = f"GRP_{master_name.replace(' ', '').upper()[:15]}"
            
            # Check if we already made it
            master_item = Item.query.filter_by(code=master_code).first()
            if not master_item:
                master_item = Item(
                    code=master_code,
                    name=f"GENEL: {master_name}",
                    price_source=PriceSource.INFERRED,
                    is_configurable=True
                )
                db.session.add(master_item)
                db.session.commit() # Commit so we get an ID

            # Get all the specific variants (e.g., 7045132, 7045133)
            variants = Item.query.filter_by(name=master_name).filter(Item.code != master_code).all()
            
            for variant in variants:
                # 1. Change the variant's name to include its specific code (e.g., "Kapak (7045132)")
                variant.name = f"{master_name} ({variant.code})"
                
                # 2. Add it as a child to the Master Group
                master_item.add_component(variant, qty=1.0)
                
        db.session.commit()
        print("✅ İsim gruplandırması tamamlandı.")

        # ==========================================
        # TASK 3: DNA Extraction (Finding codes hidden in names)
        # ==========================================
        print("🧬 Adım 2: İsimlerden DNA Çıkarımı...")
        
        # Example: Looking for patterns like "M7045" or "D87" buried in names
        # We will scan items that don't have children yet
        raw_items = Item.query.filter(~Item.children_links.any()).all()
        
        extracted_count = 0
        for item in raw_items:
            # Look for a common legacy pattern (e.g., starts with M, 4 numbers, 1 letter)
            # You can tweak this regex based on what you see in the UI!
            match = re.search(r'(M\d{4}[A-Z]\d{2})', item.name)
            
            if match:
                hidden_code = match.group(1)
                
                # Does this hidden code exist in our database as a real item?
                dna_component = Item.query.filter_by(code=hidden_code).first()
                
                if dna_component and dna_component.item_id != item.item_id:
                    print(f"  -> DNA Bulundu: {item.name} aslında {hidden_code} içeriyor.")
                    item.add_component(dna_component, qty=1.0)
                    extracted_count += 1
                    
        db.session.commit()
        print(f"✅ {extracted_count} öğe isimden analiz edilerek kompozisyona dönüştürüldü.")
        print("🎉 Temizlik Tamamlandı!")