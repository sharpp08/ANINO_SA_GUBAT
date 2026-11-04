"""
Headless test suite for the update and compatibility system (patcher & manifest).

Run: python tests/test_update_system.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tools.manifest import generate_manifest, verify_manifest, sha256_file
from tools.patcher import parse_unified_diff, apply_file_patch, FilePatch, Hunk


def test_manifest_generation_and_verification():
    with tempfile.TemporaryDirectory() as tmp:
        # Create a dummy python file
        dummy_py = os.path.join(tmp, 'main.py')
        with open(dummy_py, 'w') as f:
            f.write("print('hello')\n")

        # Generate manifest
        manifest = generate_manifest(tmp, version="BUILD TEST")
        assert manifest['version'] == "BUILD TEST"
        assert 'main.py' in manifest['files']

        # Verify should pass
        report = verify_manifest(tmp)
        assert report['ok'] is True
        assert report['verified'] == 1

        # Corrupt file
        with open(dummy_py, 'w') as f:
            f.write("print('corrupted')\n")

        report_bad = verify_manifest(tmp)
        assert report_bad['ok'] is False
        assert 'main.py' in report_bad['mismatches']
        print("[OK] Manifest generation and verification test passed")


def test_patcher_parsing_and_application():
    with tempfile.TemporaryDirectory() as tmp:
        target_path = os.path.join(tmp, 'game_config.py')
        with open(target_path, 'w') as f:
            f.write("VERSION = '1.0'\nDEBUG = False\n")

        # Construct a FilePatch directly
        patch = FilePatch(
            old_path='game_config.py',
            new_path='game_config.py',
            hunks=[
                Hunk(
                    old_start=1,
                    old_count=2,
                    new_start=1,
                    new_count=2,
                    lines=[
                        ('-', "VERSION = '1.0'"),
                        ('+', "VERSION = '2.0'"),
                        (' ', "DEBUG = False"),
                    ]
                )
            ]
        )

        ok, msg = apply_file_patch(patch, tmp, dry_run=False)
        assert ok is True

        with open(target_path, 'r') as f:
            content = f.read()
        assert "VERSION = '2.0'" in content
        print("✓ Patcher test passed")


if __name__ == '__main__':
    test_manifest_generation_and_verification()
    test_patcher_parsing_and_application()
    print("ALL UPDATE SYSTEM TESTS PASSED ✅")
