import os


def inject_content(master_file, specs_dir):
    with open(master_file, 'r', encoding='utf-8') as f:
        data = f.read()
    
    sections = data.split('[[SECTION_BREAK]]')
    for section in sections:
        if 'xcode: ' in section:
            # Extract xcode
            xcode = section.split('xcode: ')[1].split('\n')[0].strip()
            target_file = os.path.join(specs_dir, f"{xcode}.md")
            
            if os.path.exists(target_file):
                with open(target_file, 'a', encoding='utf-8') as f:
                    f.write("\n" + section.split(xcode)[1].strip())
                print(f"✅ Injected content into {xcode}.md")

# Run it
inject_content('adddetails.txt', '../content/specs')