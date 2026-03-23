import hashlib
import os


def run_integrity_audit(specs_dir):
    files = [f for f in os.listdir(specs_dir) if f.endswith('.md')]
    content_hashes = {}
    duplicates = []
    incomplete = []

    print(f"--- 🔍 Auditing {len(files)} Specifications ---\n")

    for filename in files:
        path = os.path.join(specs_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Check for Metadata Completeness
        if 'tr_category:' not in content or 'ifc_class:' not in content:
            incomplete.append(f"{filename} (Missing Metadata)")

        # 2. Extract technical body (ignoring titles and metadata for hash)
        body = content.split('---')[-1].strip()
        
        if len(body) < 50: # Threshold for 'too short'
            incomplete.append(f"{filename} (Body too short/empty)")
            continue

        # 3. Duplicate Detection (Hashing the technical body)
        body_hash = hashlib.md5(body.encode('utf-8')).hexdigest()
        if body_hash in content_hashes:
            duplicates.append((filename, content_hashes[body_hash]))
        else:
            content_hashes[body_hash] = filename

    # --- REPORT ---
    if duplicates:
        print("❌ DUPLICATES FOUND:")
        for dup in duplicates:
            print(f"   > {dup[0]} is identical to {dup[1]}")
    else:
        print("✅ No duplicate technical descriptions found.")

    if incomplete:
        print("\n⚠️  INCOMPLETE FILES:")
        for item in incomplete:
            print(f"   > {item}")
    else:
        print("✅ All files meet metadata and length requirements.")

# Execute
specs_path = os.path.join('..', 'content', 'specs')
run_integrity_audit(specs_path)