"""Pure-Python unified-diff patcher."""
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[Tuple[str, str]] = field(default_factory=list)

@dataclass
class FilePatch:
    old_path: str
    new_path: str
    is_new_file: bool = False
    is_deleted: bool = False
    hunks: List[Hunk] = field(default_factory=list)

def parse_unified_diff(diff_text: str) -> List[FilePatch]:
    lines = diff_text.splitlines()
    patches, current, current_hunk, i = [], None, None, 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('diff --git '):
            if current_hunk and current:
                current.hunks.append(current_hunk); current_hunk = None
            if current: patches.append(current)
            m = re.match(r'^diff --git a/(.+?) b/(.+)$', line)
            current = FilePatch(old_path=m.group(1), new_path=m.group(2)) if m else FilePatch(old_path='', new_path='')
            i += 1; continue
        if line.startswith('new file mode'):
            if current: current.is_new_file = True
            i += 1; continue
        if line.startswith('deleted file mode'):
            if current: current.is_deleted = True
            i += 1; continue
        if line.startswith(('index ', 'similarity ', 'rename ', 'copy ')):
            i += 1; continue
        if line.startswith('--- '):
            p = line[4:]
            if p != '/dev/null' and current: current.old_path = p[2:] if p.startswith('a/') else p
            i += 1; continue
        if line.startswith('+++ '):
            p = line[4:]
            if p != '/dev/null' and current: current.new_path = p[2:] if p.startswith('b/') else p
            i += 1; continue
        hunk_match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        if hunk_match:
            if current_hunk and current: current.hunks.append(current_hunk)
            current_hunk = Hunk(
                old_start=int(hunk_match.group(1)),
                old_count=int(hunk_match.group(2)) if hunk_match.group(2) else 1,
                new_start=int(hunk_match.group(3)),
                new_count=int(hunk_match.group(4)) if hunk_match.group(4) else 1,
            )
            i += 1; continue
        if current_hunk is not None:
            if line.startswith('\\') and 'No newline' in line:
                i += 1; continue
            if len(line) == 0:
                current_hunk.lines.append((' ', ''))
                i += 1; continue
            prefix, text = line[0], line[1:]
            if prefix in (' ', '-', '+'):
                current_hunk.lines.append((prefix, text))
            i += 1; continue
        i += 1
    if current_hunk and current: current.hunks.append(current_hunk)
    if current: patches.append(current)
    return patches


def _fuzzy_find(lines, target, expected_pos, fuzz=5):
    for delta in range(-fuzz, fuzz + 1):
        pos = expected_pos + delta
        if pos < 0: continue
        ok = True
        for j, expected in enumerate(target):
            if pos + j >= len(lines) or lines[pos + j] != expected:
                ok = False; break
        if ok: return pos
    return None

def apply_file_patch(patch: FilePatch, base_dir: str = '.', dry_run: bool = False) -> Tuple[bool, str]:
    full_path = os.path.join(base_dir, patch.new_path)
    if patch.is_new_file:
        if os.path.exists(full_path): return True, f"already exists: {patch.new_path}"
        if dry_run: return True, f"would create: {patch.new_path}"
        content_lines = [t for h in patch.hunks for pfx, t in h.lines if pfx in (' ', '+')]
        os.makedirs(os.path.dirname(full_path) or '.', exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_lines) + ('\n' if content_lines else ''))
        return True, f"created: {patch.new_path}"
    if patch.is_deleted:
        if not os.path.exists(full_path): return True, f"already deleted: {patch.new_path}"
        if dry_run: return True, f"would delete: {patch.new_path}"
        os.remove(full_path)
        return True, f"deleted: {patch.new_path}"
    if not os.path.exists(full_path): return False, f"file not found: {patch.new_path}"
    with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
    result, offset, applied, skipped = content.split('\n'), 0, 0, 0
    for hunk in patch.hunks:
        old_lines = [t for pfx, t in hunk.lines if pfx in (' ', '-')]
        new_lines = [t for pfx, t in hunk.lines if pfx in (' ', '+')]
        pos = hunk.old_start + offset if hunk.old_count == 0 else hunk.old_start - 1 + offset
        matched = pos >= 0
        for j, exp in enumerate(old_lines):
            if pos + j >= len(result) or result[pos + j] != exp:
                matched = False; break
        if matched:
            result[pos:pos + len(old_lines)] = new_lines
            offset += len(new_lines) - len(old_lines)
            applied += 1; continue
        already = True
        for j, exp in enumerate(new_lines):
            if pos + j >= len(result) or result[pos + j] != exp:
                already = False; break
        if already:
            skipped += 1; continue
        fp = _fuzzy_find(result, old_lines, pos)
        if fp is not None:
            result[fp:fp + len(old_lines)] = new_lines
            offset += len(new_lines) - len(old_lines) + (fp - pos)
            applied += 1; continue
        return False, f"hunk @ line {hunk.old_start} failed in {patch.new_path}"
    if dry_run: return True, f"would patch: {patch.new_path} ({applied} apply, {skipped} skip)"
    with open(full_path, 'w', encoding='utf-8') as f: f.write('\n'.join(result))
    return True, f"patched: {patch.new_path} ({applied} apply, {skipped} skip)"

def apply_diff_file(diff_path: str, base_dir: str = '.', dry_run: bool = False) -> Tuple[bool, list]:
    with open(diff_path, 'r', encoding='utf-8') as f: diff_text = f.read()
    patches = parse_unified_diff(diff_text)
    results = []
    all_ok = True
    for patch in patches:
        ok, msg = apply_file_patch(patch, base_dir, dry_run)
        results.append((ok, msg))
        if not ok: all_ok = False
    return all_ok, results

