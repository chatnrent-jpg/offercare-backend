#!/usr/bin/env python3
"""
Complete VettedMe to VettedMe Rebrand Script
Replaces all instances across the entire codebase
"""

import os
import re
from pathlib import Path

# Replacement mappings
REPLACEMENTS = [
    ("VettedMe", "VettedMe"),
    ("vettedme", "vettedme"),
    ("VETTEDME", "VETTEDME"),
]

# File extensions to process
EXTENSIONS = [
    ".py", ".md", ".json", ".yml", ".yaml", ".txt", ".sh", ".bat",
    ".ps1", ".sql", ".ini", ".html", ".js", ".css", ".tf", ".env"
]

# Directories to skip
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache", "venv", ".venv"}

def should_process_file(filepath):
    """Check if file should be processed"""
    # Skip if in excluded directory
    for skip_dir in SKIP_DIRS:
        if skip_dir in filepath.parts:
            return False
    
    # Check extension
    return filepath.suffix in EXTENSIONS or filepath.name in [
        ".env", ".env.example", ".env.production", "Dockerfile"
    ]

def rebrand_file(filepath):
    """Replace VettedMe with VettedMe in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply all replacements
        for old, new in REPLACEMENTS:
            content = content.replace(old, new)
        
        # Only write if changes were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Main rebrand execution"""
    root = Path.cwd()
    files_changed = 0
    
    print("Starting VettedMe -> VettedMe rebrand...")
    print("")
    
    for filepath in root.rglob("*"):
        if filepath.is_file() and should_process_file(filepath):
            if rebrand_file(filepath):
                print(f"[OK] {filepath.relative_to(root)}")
                files_changed += 1
    
    print("")
    print(f"Rebrand complete! {files_changed} files updated.")

if __name__ == "__main__":
    main()
