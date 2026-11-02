"""
Game Update and Compatibility Tool for ANINO SA GUBAT.

Commands:
    python tools/update_game.py status            - Show version and file integrity status
    python tools/update_game.py manifest          - Generate new integrity manifest.json
    python tools/update_game.py verify            - Verify game file integrity against manifest
    python tools/update_game.py backup            - Create backup zip of current code/saves
    python tools/update_game.py patch <file.patch>- Apply a unified diff patch file
    python tools/update_game.py migrate-settings  - Ensure settings.json is compatible
    python tools/update_game.py deps              - Install / update python dependencies
    python tools/update_game.py build             - Build standalone .exe via PyInstaller
    python tools/update_game.py update            - Run full update pipeline (verify, patch, deps, build)
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from settings import BUILD_VERSION, BASE_PATH, load_settings, save_settings
from tools.manifest import generate_manifest, verify_manifest
from tools.patcher import apply_diff_file


def cmd_status(args):
    print(f"=== ANINO SA GUBAT: UPDATE & COMPATIBILITY STATUS ===")
    print(f"Current Build Version: {BUILD_VERSION}")
    print(f"Base Directory: {BASE_PATH}")
    
    manifest_path = os.path.join(BASE_PATH, 'manifest.json')
    if os.path.exists(manifest_path):
        report = verify_manifest(BASE_PATH)
        print(f"Manifest Version: {report.get('version', '?')}")
        print(f"Files Verified: {report['verified']}")
        print(f"Mismatches: {len(report['mismatches'])}")
        print(f"Missing: {len(report['missing'])}")
        print(f"Integrity Status: {'PASSED ✅' if report['ok'] else 'FAILED ❌'}")
    else:
        print("Manifest: not found (run 'manifest' command to create)")

    exe_path = os.path.join(BASE_PATH, 'dist', 'ANINO_SA_GUBAT.exe')
    if os.path.exists(exe_path):
        mtime = os.path.getmtime(exe_path)
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        dt = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Executable: dist/ANINO_SA_GUBAT.exe ({size_mb:.1f} MB, built {dt})")
    else:
        print("Executable: dist/ANINO_SA_GUBAT.exe not found (run 'build' command)")


def cmd_manifest(args):
    print(f"Generating integrity manifest for version {BUILD_VERSION}...")
    manifest = generate_manifest(BASE_PATH, BUILD_VERSION)
    print(f"Manifest generated successfully with {len(manifest['files'])} tracked files.")


def cmd_verify(args):
    print("Verifying game file integrity...")
    report = verify_manifest(BASE_PATH)
    print(f"Version in Manifest: {report.get('version', '?')}")
    print(f"Verified OK: {report['verified']}")
    if report['mismatches']:
        print(f"Mismatched files ({len(report['mismatches'])}):")
        for f in report['mismatches']:
            print(f"  ❌ {f}")
    if report['missing']:
        print(f"Missing files ({len(report['missing'])}):")
        for f in report['missing']:
            print(f"  ❌ {f}")
    if report['extra']:
        print(f"Extra untracked files ({len(report['extra'])}):")
        for f in report['extra']:
            print(f"  ℹ️ {f}")
    
    if report['ok']:
        print("Integrity Check: PASSED ✅")
    else:
        print("Integrity Check: FAILED ❌ (files have been modified or corrupted)")
        sys.exit(1)


def cmd_backup(args):
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(BASE_PATH, 'release')
    os.makedirs(backup_dir, exist_ok=True)
    zip_path = os.path.join(backup_dir, f'backup_{BUILD_VERSION.replace(" ", "_")}_{ts}.zip')
    
    print(f"Creating backup archive at {zip_path}...")
    excluded_dirs = {'__pycache__', '.venv', 'build', 'dist', '.git', 'saves'}
    count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BASE_PATH):
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, BASE_PATH)
                if file.endswith('.zip') or file.endswith('.exe'):
                    continue
                zf.write(full_path, rel_path)
                count += 1
    print(f"Backup complete: {count} files archived ({os.path.getsize(zip_path)/(1024*1024):.1f} MB).")



def cmd_patch(args):
    patch_path = args.patch_file
    if not os.path.exists(patch_path):
        alt = os.path.join(BASE_PATH, 'Patch file', patch_path)
        if os.path.exists(alt):
            patch_path = alt
        else:
            print(f"Error: Patch file not found: {args.patch_file}")
            sys.exit(1)
    
    print(f"Applying patch: {patch_path} (dry_run={args.dry_run})...")
    ok, results = apply_diff_file(patch_path, BASE_PATH, dry_run=args.dry_run)
    for file_ok, msg in results:
        prefix = "✅" if file_ok else "❌"
        print(f"  {prefix} {msg}")
    
    if not ok:
        print("Patch application FAILED ❌")
        sys.exit(1)
    else:
        print("Patch application SUCCESSFUL ✅")


def cmd_migrate_settings(args):
    print("Checking and migrating settings.json compatibility...")
    settings = load_settings()
    save_settings(settings)
    print(f"Settings migrated successfully. Quality tier: {settings.get('quality_tier', 'medium')}")


def cmd_deps(args):
    req_path = os.path.join(BASE_PATH, 'requirements.txt')
    if not os.path.exists(req_path):
        print("No requirements.txt found.")
        return
    
    python_exe = sys.executable
    print(f"Updating Python dependencies using {python_exe}...")
    cmd = [python_exe, '-m', 'pip', 'install', '-r', req_path, '--upgrade']
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("Dependencies updated successfully ✅")
    else:
        print("Dependency update failed ❌")
        sys.exit(res.returncode)


def cmd_build(args):
    spec_path = os.path.join(BASE_PATH, 'ANINO_SA_GUBAT.spec')
    if not os.path.exists(spec_path):
        print(f"Error: Spec file not found: {spec_path}")
        sys.exit(1)
    
    python_exe = sys.executable
    print(f"Building standalone executable with PyInstaller...")
    cmd = [python_exe, '-m', 'PyInstaller', spec_path, '--noconfirm']
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("Build SUCCESSFUL ✅ Executable updated at dist/ANINO_SA_GUBAT.exe")
    else:
        print("Build FAILED ❌")
        sys.exit(res.returncode)


def cmd_update(args):
    print(f"=== RUNNING FULL UPDATE PIPELINE FOR {BUILD_VERSION} ===")
    cmd_migrate_settings(args)
    cmd_deps(args)
    if not getattr(args, 'skip_verify', False):
        try:
            cmd_verify(args)
        except SystemExit:
            print("Pre-verification failed. Proceeding with update...")
    cmd_build(args)
    cmd_manifest(args)
    print("=== FULL UPDATE PIPELINE COMPLETE ✅ ===")


def main():
    parser = argparse.ArgumentParser(description="ANINO SA GUBAT Update & Compatibility Tool")
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('status', help='Show build and integrity status')
    subparsers.add_parser('manifest', help='Generate integrity manifest.json')
    subparsers.add_parser('verify', help='Verify file integrity against manifest')
    subparsers.add_parser('backup', help='Create backup archive')

    p_patch = subparsers.add_parser('patch', help='Apply unified diff patch file')
    p_patch.add_argument('patch_file', help='Path to .patch file')
    p_patch.add_argument('--dry-run', action='store_true', help='Simulate patch without writing')

    subparsers.add_parser('migrate-settings', help='Migrate settings.json compatibility')
    subparsers.add_parser('deps', help='Update Python dependencies from requirements.txt')
    subparsers.add_parser('build', help='Rebuild standalone .exe via PyInstaller')

    p_update = subparsers.add_parser('update', help='Run full update pipeline')
    p_update.add_argument('--skip-verify', action='store_true', help='Skip pre-verification')

    args = parser.parse_args()

    commands = {
        'status': cmd_status,
        'manifest': cmd_manifest,
        'verify': cmd_verify,
        'backup': cmd_backup,
        'patch': cmd_patch,
        'migrate-settings': cmd_migrate_settings,
        'deps': cmd_deps,
        'build': cmd_build,
        'update': cmd_update,
    }

    fn = commands.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
