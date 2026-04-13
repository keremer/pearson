import os
import re
from typing import Optional

import pandas as pd

from crminaec.core.models import db
from crminaec.platforms.emek.models import Item, ItemComposition


# =====================================================================
# 1. TAXONOMY & SAFETY
# =====================================================================
def safe_float(val) -> float:
    if pd.isna(val) or str(val).strip() == '': return 0.0
    try: return float(str(val).replace(',', '.').strip())
    except ValueError: return 0.0

def is_circular(parent: Item, child: Item) -> bool:
    p_id, c_id = parent.item_id, child.item_id
    if p_id is None or c_id is None: return False
    
    stack = [p_id]
    visited = {p_id}
    while stack:
        curr = stack.pop()
        if curr == c_id: return True
        parents = db.session.query(ItemComposition.parent_id).filter_by(child_id=curr).all()
        for r in parents:
            if r[0] not in visited:
                visited.add(r[0])
                stack.append(r[0])
    return False

def get_or_create_folder(code: str, name: str, parent: Optional[Item] = None) -> Item:
    f_code, f_name = str(code).strip(), str(name).strip()
    folder = db.session.query(Item).filter_by(code=f_code).first()
    
    if not folder:
        folder = Item(code=f_code, name=f_name, is_category=True)
        db.session.add(folder)
        db.session.flush()

    if parent and parent.item_id != folder.item_id:
        if not is_circular(parent, folder):
            link = db.session.query(ItemComposition).filter_by(
                parent_id=parent.item_id, child_id=folder.item_id).first()
            if not link:
                db.session.add(ItemComposition(parent_item=parent, child_item=folder, quantity=1.0))
                db.session.flush()
    return folder

# =====================================================================
# 2. PHASE 1: PRE-GENERATE CATEGORIES
# =====================================================================
def build_category_tree(data_folder: str) -> dict:
    path = os.path.join(data_folder, 'urun_grup_new.csv')
    if not os.path.exists(path):
        print(f"❌ ERROR: {path} not found!")
        return {}
    
    # utf-8-sig strips the hidden BOM (\ufeff) from Excel exports
    df = pd.read_csv(path, sep=None, engine='python', dtype=str, encoding='utf-8-sig').fillna('')
    df.columns = [c.lower().strip() for c in df.columns]
    
    print("📂 PHASE 1: Building Root Categories...")
    ug_map = {}
    for _, row in df.iterrows():
        ug_code = str(row.get('ug', '')).strip()
        if ug_code:
            name = str(row.get('ugack', f'Grup {ug_code}')).strip()
            root = str(row.get('grup', 'Genel')).strip()
            
            ug_map[ug_code] = {'name': name, 'root': root}
            
            # Create Hierarchy
            root_folder = get_or_create_folder(f"ROOT_{root.upper()}", root)
            get_or_create_folder(f"UG_{ug_code}", name, root_folder)

    # SECURE THE CATEGORIES IN THE DATABASE IMMEDIATELY
    db.session.commit()
    print(f"✅ Created {len(ug_map)} Categories permanently in the database.")
    return ug_map

# =====================================================================
# 3. PHASE 2: IMPORT ITEMS & BOM
# =====================================================================
def run_master_import():
    data_folder = 'legacy_data'
    
    # 1. Create all folders first
    UG_MAPPINGS = build_category_tree(data_folder)
    if not UG_MAPPINGS: return

    # 2. Import Physical Items
    urun_path = os.path.join(data_folder, 'urun.csv')
    if os.path.exists(urun_path):
        print("📦 PHASE 2: Processing urun.csv...")
        df_urun = pd.read_csv(urun_path, sep=None, engine='python', dtype=str, encoding='utf-8-sig').fillna('')
        df_urun.columns = [c.lower().strip() for c in df_urun.columns]
        
        for index, row in df_urun.iterrows():
            urk = str(row.get('urk', '')).strip()
            ura = str(row.get('ura', 'İsimsiz Öğe')).strip()
            row_ug = str(row.get('ug', '')).strip()
            
            if not urk: continue

            # Create or update Item
            item = db.session.query(Item).filter_by(code=urk).first()
            if not item:
                item = Item(
                    code=urk, 
                    name=ura,
                    dim_x=safe_float(row.get('byt_x')),
                    dim_y=safe_float(row.get('byt_y')),
                    dim_z=safe_float(row.get('byt_z')),
                    technical_specs={"Eski_UG": row_ug}
                )
                db.session.add(item)
                db.session.flush()
                
            # Link to Pre-Existing Category
            if row_ug:
                cat_folder = db.session.query(Item).filter_by(code=f"UG_{row_ug}").first()
                if cat_folder and not is_circular(cat_folder, item):
                    link = db.session.query(ItemComposition).filter_by(
                        parent_id=cat_folder.item_id, child_id=item.item_id).first()
                    if not link:
                        db.session.add(ItemComposition(parent_item=cat_folder, child_item=item, quantity=1.0))
        
        # Commit all items safely
        db.session.commit()
        print("✅ urun.csv imported successfully.")

    # 3. Import Static BoM Links
    agac_path = os.path.join(data_folder, 'urun_agac.csv')
    if os.path.exists(agac_path):
        print("🔗 PHASE 3: Linking urun_agac.csv...")
        df_agac = pd.read_csv(agac_path, sep=None, engine='python', dtype=str, encoding='utf-8-sig').fillna('')
        df_agac.columns = [c.lower().strip() for c in df_agac.columns]
        
        for _, row in df_agac.iterrows():
            p_code = str(row.get('urk2', '')).strip()
            c_code = str(row.get('urk', '')).strip()
            qty = safe_float(row.get('miktar', 1))

            if not p_code or not c_code: continue

            parent = db.session.query(Item).filter_by(code=p_code).first()
            child = db.session.query(Item).filter_by(code=c_code).first()

            if parent and child and parent.item_id != child.item_id:
                if not is_circular(parent, child):
                    link = db.session.query(ItemComposition).filter_by(
                        parent_id=parent.item_id, child_id=child.item_id).first()
                    if not link:
                        db.session.add(ItemComposition(parent_item=parent, child_item=child, quantity=qty))
        
        db.session.commit()
        print("✅ BoM Links established.")

    print("🎉 MIGRATION COMPLETE! Open the BOM Editor to view your hierarchy.")