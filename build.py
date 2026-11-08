#!/usr/bin/env python3
"""
Build script for Game Mode.
Usage: python build.py [--version X.Y.Z] [--no-movement-helper]
"""

import argparse
import subprocess
import sys
from pathlib import Path

def run(cmd, cwd=None, check=True):
    """Run command and return result"""
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result

def extract_version(app_file: Path) -> str:
    """Extract APP_VERSION from gamemode_app.py"""
    content = app_file.read_text(encoding='utf-8')
    import re
    match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    raise ValueError("Could not find APP_VERSION in gamemode_app.py")

def main():
    parser = argparse.ArgumentParser(description='Build Game Mode installer')
    parser.add_argument('--version', help='Override version (default: from gamemode_app.py)')
    parser.add_argument('--no-movement-helper', action='store_true', help='Build without SOCD cleaner')
    parser.add_argument('--skip-nuitka', action='store_true', help='Skip Nuitka compilation')
    parser.add_argument('--skip-nsis', action='store_true', help='Skip NSIS installer build')
    args = parser.parse_args()

    repo_root = Path(__file__).parent
    app_file = repo_root / 'gamemode_app.py'

    # Get version
    version = args.version or extract_version(app_file)
    print(f"Building version: {version}")

    # Build output names
    exe_name = f"GameMode.exe"
    installer_name = f"Instalar_GameMode_{version}.exe"
    build_dir = repo_root / 'build'
    dist_dir = build_dir / f'gamemode_app.dist'

    # 1. Compile with Nuitka
    if not args.skip_nuitka:
        print("\n=== Compiling with Nuitka ===")
        nuitka_args = [
            sys.executable, '-m', 'nuitka',
            '--standalone',
            '--windows-console-mode=disable',
            '--enable-plugin=tk-inter',
            '--include-package=i18n',
            '--include-package=theme_manager',
            '--include-package=game_detector',
            '--include-data-dir=i18n=i18n',
            f'--output-dir={build_dir}',
            '--remove-output',
            '--assume-yes-for-downloads',
            '--windows-icon-from-ico=app.ico',
            '--company-name=RegenKaboom',
            '--product-name=Game Mode',
            f'--file-version={version}',
            f'--product-version={version}',
            '--copyright="Copyright (C) 2024 RegenKaboom"',
        ]

        if args.no_movement_helper:
            nuitka_args.extend(['--nofollow-import-to=gm_mods', '--nofollow-import-to=MovementHelper'])
        else:
            nuitka_args.append('--include-module=gm_mods')

        nuitka_args.append('gamemode_app.py')

        run(' '.join(nuitka_args), cwd=repo_root)

    # Verify executable
    exe_path = dist_dir / exe_name
    if not exe_path.exists():
        print(f"ERROR: Executable not found at {exe_path}")
        sys.exit(1)

    print(f"\nExecutable: {exe_path} ({(exe_path.stat().st_size / 1024 / 1024):.1f} MB)")

    # 2. Build installer with NSIS
    if not args.skip_nsis:
        print("\n=== Building installer with NSIS ===")

        # Check for NSIS
        nsis_path = Path(r"C:\Program Files (x86)\NSIS\makensis.exe")
        if not nsis_path.exists():
            nsis_path = Path(r"C:\Program Files\NSIS\makensis.exe")

        if not nsis_path.exists():
            print("NSIS not found. Install with: choco install nsis")
            sys.exit(1)

        nsis_cmd = [
            str(nsis_path),
            f'/DAPP_VERSION={version}',
            f'/DOUTFILE={installer_name}',
            'GameMode.nsi'
        ]

        run(' '.join(f'"{arg}"' if ' ' in arg else arg for arg in nsis_cmd), cwd=repo_root)

        installer_path = repo_root / installer_name
        if installer_path.exists():
            print(f"\nInstaller: {installer_path} ({(installer_path.stat().st_size / 1024 / 1024):.1f} MB)")
        else:
            print("ERROR: Installer not created!")
            sys.exit(1)

    # 3. Generate latest.json
    print("\n=== Generating latest.json ===")
    import hashlib
    import json
    from datetime import datetime

    if not args.skip_nsis:
        installer_path = repo_root / installer_name
        sha256 = hashlib.sha256(installer_path.read_bytes()).hexdigest()

        # Get changelog
        changelog = ""
        novidades = repo_root / 'novidades.txt'
        if novidades.exists():
            changelog = novidades.read_text(encoding='utf-8')
            if len(changelog) > 500:
                changelog = changelog[:500] + "..."

        latest = {
            'version': version,
            'url': f'https://github.com/RegenKaboom/gamemode/releases/download/v{version}/{installer_name}',
            'sha256': sha256,
            'notes': changelog,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

        (repo_root / 'latest.json').write_text(json.dumps(latest, indent=2), encoding='utf-8')
        print(f"latest.json created with SHA256: {sha256[:16]}...")

    print("\n=== Build Complete ===")
    print(f"Version: {version}")
    print(f"Executable: {exe_path}")
    if not args.skip_nsis:
        print(f"Installer: {repo_root / installer_name}")
        print(f"latest.json: {repo_root / 'latest.json'}")

if __name__ == '__main__':
    main()