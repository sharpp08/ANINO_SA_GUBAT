"""
File integrity manifest: generate and verify SHA-256 checksums for game files.

The manifest (manifest.json) records the build version, generation timestamp,
and a SHA-256 hash + size for every tracked source and asset file.  Before and
after patching, verify() compares the on-disk files against the manifest so
corrupted or incomplete updates are caught immediately.
"""
import hashlib
import json
import os
from datetime import datetime, timezone


def sha256_file(path: str) -> str:
    """Compute the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def collect_tracked_files(base_dir: str) -> list:
    """Collect all game source and asset files relative to base_dir."""
    tracked = set()

    # Root-level Python, spec, and requirements files
    for f in os.listdir(base_dir):
        full = os.path.join(base_dir, f)
        if os.path.isfile(full) and (
            f.endswith('.py') or f.endswith('.spec') or f == 'requirements.txt'
        ):
            tracked.add(f)

    # Python files in tools/ and tests/
    for subdir in ('tools', 'tests'):
        d = os.path.join(base_dir, subdir)
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith('.py'):
                    tracked.add(os.path.join(subdir, f))

    # Asset files (audio, sprites) — excludes cache/ which is generated
    for subdir in ('assets/audio', 'assets/sprites'):
        d = os.path.join(base_dir, subdir)
        if os.path.isdir(d):
            for root, _dirs, files in os.walk(d):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), base_dir)
                    tracked.add(rel.replace('\\', '/'))

    return sorted(tracked)


def generate_manifest(base_dir: str, version: str,
                       manifest_path: str = None) -> dict:
    """Generate a manifest.json with SHA-256 hashes of all tracked files."""
    if manifest_path is None:
        manifest_path = os.path.join(base_dir, 'manifest.json')

    files = collect_tracked_files(base_dir)
    file_info = {}
    for rel_path in files:
        full_path = os.path.join(base_dir, rel_path)
        if os.path.isfile(full_path):
            file_info[rel_path] = {
                'sha256': sha256_file(full_path),
                'size': os.path.getsize(full_path),
            }

    manifest = {
        'version': version,
        'generated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'files': file_info,
    }

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    return manifest


def verify_manifest(base_dir: str, manifest_path: str = None) -> dict:
    """Verify files against manifest. Returns a report dict."""
    if manifest_path is None:
        manifest_path = os.path.join(base_dir, 'manifest.json')

    if not os.path.exists(manifest_path):
        return {'ok': False, 'error': 'manifest.json not found',
                'verified': 0, 'mismatches': [], 'missing': [], 'extra': []}

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    expected = manifest.get('files', {})
    mismatches = []
    missing = []
    verified = 0

    for rel_path, info in expected.items():
        full_path = os.path.join(base_dir, rel_path)
        if not os.path.exists(full_path):
            missing.append(rel_path)
            continue
        actual_hash = sha256_file(full_path)
        if actual_hash != info['sha256']:
            mismatches.append(rel_path)
        else:
            verified += 1

    # Check for extra files not in manifest
    tracked = set(collect_tracked_files(base_dir))
    expected_set = set(expected.keys())
    extra = sorted(tracked - expected_set)

    return {
        'ok': len(mismatches) == 0 and len(missing) == 0,
        'version': manifest.get('version', '?'),
        'generated': manifest.get('generated', '?'),
        'verified': verified,
        'mismatches': mismatches,
        'missing': missing,
        'extra': extra,
    }
