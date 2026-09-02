import os
import re

tasks_dir = '/workspace/second-brain/Tasks/'

def clean_and_renumber():
    files = [f for f in os.listdir(tasks_dir) if os.path.isfile(os.path.join(tasks_dir, f))]
    
    # 1. Strip leading numbers and dots
    # Pattern: starts with optional digits, then optional dot, then optional space
    pattern = re.compile(r'^\d+\.\s*')
    
    cleaned_files = []
    for f in files:
        new_name = pattern.sub('', f)
        # Also handle cases like "~ARCHIVED." or "Implement ..."
        cleaned_files.append((f, new_name))
    
    # Sort by the cleaned name to keep it somewhat logical
    cleaned_files.sort(key=lambda x: x[1])
    
    # 2. Rename to temporary names to avoid collisions
    temp_files = []
    for old_name, clean_name in cleaned_files:
        temp_name = f"temp_{os.urandom(4).hex()}_{clean_name}"
        os.rename(os.path.join(tasks_dir, old_name), os.path.join(tasks_dir, temp_name))
        temp_files.append((temp_name, clean_name))
        
    # 3. Rename to final sequential numbers
    for i, (temp_name, clean_name) in enumerate(temp_files, 1):
        final_name = f"{i}. {clean_name}"
        os.rename(os.path.join(tasks_dir, temp_name), os.path.join(tasks_dir, final_name))
        print(f"Renamed: {old_name if 'old_name' in locals() else ''} -> {final_name}")

if __name__ == '__main__':
    clean_and_renumber()
