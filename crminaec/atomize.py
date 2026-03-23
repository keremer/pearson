import os

def process_master_lib(file_path, output_dir):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    sections = content.split('[[SECTION_BREAK]]')
    for section in sections:
        if 'xcode: ' in section:
            # Extract xcode for the filename
            xcode = section.split('xcode: ')[1].split('\n')[0].strip()
            with open(os.path.join(output_dir, f"{xcode}.md"), 'w', encoding='utf-8') as out:
                out.write(section.strip())
            print(f"✅ Deployed: {xcode}.md")

# Usage
process_master_lib('master_lib.txt', '../content/specs')