import os

import click
import pandas as pd
from sqlalchemy.exc import IntegrityError

from crminaec.core.database import db
from crminaec.platforms.emek.models import Item, PriceSource


def run_import(app, data_dir):
    """Executes the legacy data migration within the Flask app context."""
    with app.app_context():
        print("🚀 Başlıyor: MS Access Legacy Data Migration (Excel)...")
        
        # In-memory cache to prevent duplicate database queries
        item_cache = {}

        # UPDATED HELPER: Accepts kwargs for the new fields
        def get_or_create_item(code, name, source=PriceSource.LEGACY, **kwargs):
            code = str(code).strip()
            if code in item_cache:
                return item_cache[code]
            
            item = db.session.query(Item).filter_by(code=code).first()
            if not item:
                item = Item(
                    code=code,
                    name=str(name).strip()[:100],
                    price_source=source,
                    reliability_score=20,
                    # Safely inject the new fields if provided, otherwise use defaults
                    product_group=kwargs.get('product_group'),
                    product_type=kwargs.get('product_type'),
                    uom=kwargs.get('uom', 'adet'),
                    dim_x=float(kwargs.get('dim_x', 0.0) or 0.0),
                    dim_y=float(kwargs.get('dim_y', 0.0) or 0.0),
                    dim_z=float(kwargs.get('dim_z', 0.0) or 0.0)
                )
                db.session.add(item)
            
            item_cache[code] = item
            return item

        # ==========================================
        # PHASE 1: Import the Atoms (Attributes & Features)
        # ==========================================
        print("📦 1. Aşama: Atomlar Yükleniyor (Renkler ve Özellikler)...")
        
        # 1A: Colors & Finishes
        nitelik_path = os.path.join(data_dir, 'nitelikdeger.xlsx')
        if os.path.exists(nitelik_path):
            df_nitelik = pd.read_excel(nitelik_path).dropna(subset=['degerkisaltma', 'degeradi'])
            for _, row in df_nitelik.iterrows():
                get_or_create_item(row['degerkisaltma'], row['degeradi'])
        
        # 1B: Features (Handles, Mechanisms)
        ozellik_path = os.path.join(data_dir, 'ozellik.xlsx')
        if os.path.exists(ozellik_path):
            df_ozellik = pd.read_excel(ozellik_path).dropna(subset=['ozk', 'oza']).drop_duplicates(subset=['ozk'])
            for _, row in df_ozellik.iterrows():
                get_or_create_item(row['ozk'], row['oza'])
        
        db.session.commit() # Commit Atoms
        print(f"✅ {len(item_cache)} Atom başarıyla oluşturuldu.")

        # ==========================================
        # PHASE 2: Import the Molecules (Products)
        # ==========================================
    
        print("🗄️ 2. Aşama: Moleküller Yükleniyor (Ana Ürünler)...")
        urun_path = os.path.join(data_dir, 'urun.xlsx')
        if os.path.exists(urun_path):
            df_urun = pd.read_excel(urun_path).dropna(subset=['urk', 'ura']).drop_duplicates(subset=['urk'])
            
            # Convert dimensions to numeric, forcing errors to NaN, then filling with 0
            df_urun['byt_x'] = pd.to_numeric(df_urun['byt_x'], errors='coerce').fillna(0)
            df_urun['byt_y'] = pd.to_numeric(df_urun['byt_y'], errors='coerce').fillna(0)
            df_urun['byt_z'] = pd.to_numeric(df_urun['byt_z'], errors='coerce').fillna(0)

            for _, row in df_urun.iterrows():
                get_or_create_item(
                    code=row['urk'], 
                    name=row['ura'],
                    product_group=str(row.get('ug', '')),
                    product_type=str(row.get('utk', '')),
                    uom=str(row.get('brm', 'adet')),
                    dim_x=row['byt_x'],
                    dim_y=row['byt_y'],
                    dim_z=row['byt_z']
                )
                
        db.session.commit() # Commit Molecules
        print(f"✅ {len(item_cache)} Toplam benzersiz öğe hafızaya alındı.")

        # ==========================================
        # PHASE 3: Build the Tree (Bill of Materials)
        # ==========================================
        print("🌳 3. Aşama: Ürün Ağacı Kuruluyor (BoM)...")
        agac_path = os.path.join(data_dir, 'urun_agac.xlsx')
        if os.path.exists(agac_path):
            df_agac = pd.read_excel(agac_path).dropna(subset=['urk', 'urk2', 'adet'])
            
            # --- NEW DATAFRAME CLEANING LOGIC ---
            # Group duplicates by Parent (urk) and Child (urk2), and sum their quantities
            df_agac['adet'] = pd.to_numeric(df_agac['adet'], errors='coerce').fillna(1.0)
            df_agac = df_agac.groupby(['urk', 'urk2'], as_index=False)['adet'].sum()
            # ------------------------------------

            links_created = 0
            for _, row in df_agac.iterrows():
                parent_code = str(row['urk']).strip()
                child_code = str(row['urk2']).strip()
                qty = float(row['adet'])

                # Only link if we successfully imported both parent and child
                if parent_code in item_cache and child_code in item_cache:
                    parent = item_cache[parent_code]
                    child = item_cache[child_code]
                    
                    try:
                        # Turn off autoflush temporarily for this operation to prevent premature DB commits
                        with db.session.no_autoflush:
                            parent.add_component(child, qty)
                            links_created += 1
                    except ValueError as e:
                        print(f"⚠️ Uyarı: Döngü tespit edildi veya eklenemedi ({parent_code} -> {child_code}): {e}")

            db.session.commit()
            print(f"✅ {links_created} Adet ağaç bağlantısı (kompozisyon) başarıyla kuruldu.")
        else:
            print("❌ urun_agac.xlsx bulunamadı, ağaç kurulamadı.")

        print("🎉 MIGRATION COMPLETE! (Veri aktarımı tamamlandı.)")