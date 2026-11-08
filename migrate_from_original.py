#!/usr/bin/env python3
"""
Migration script to copy files from original gamemode repo to new i18n structure.
Run this after cloning both repos.
"""

import shutil
from pathlib import Path

def main():
    # Paths
    original_repo = Path.home() / 'gamemode'  # Original cloned repo
    new_repo = Path(__file__).parent  # This repo (gamemode-i18n)

    if not original_repo.exists():
        print(f"Original repo not found at {original_repo}")
        print("Clone it first: git clone https://github.com/RegenKaboom/gamemode")
        return

    files_to_copy = [
        'gm_extras.py',
        'gm_mods.py',
        'app.ico',
        'welcome.bmp',
        'novidades.txt',
        'atualizar.txt',
        'LICENSE',
    ]

    for fname in files_to_copy:
        src = original_repo / fname
        dst = new_repo / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"Copied: {fname}")
        else:
            print(f"Missing: {fname}")

    # Also copy any assets
    assets_src = original_repo / 'assets'
    if assets_src.exists():
        assets_dst = new_repo / 'assets'
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)
        print("Copied: assets/")

    print("\nMigration complete!")
    print("Now you can build with the new structure.")

if __name__ == '__main__':
    main()