"""Locate bundled game assets whether running from source or as a PyInstaller exe.

A PyInstaller --onefile build unpacks bundled data into a temporary folder
(sys._MEIPASS); a --onedir build puts it in an `_internal` folder; and the
shipped exe also sits next to a real `assets/` directory.  Resolving paths from
`__file__` alone only finds the first of those, which is how recorded audio
(shotgun, revolver, ...) could silently go missing in the exe.

Every lookup tries each location in order and returns the first one that really
contains the file, so the exe picks audio up from the bundle *or* from the
`assets/` folder next to it.
"""
import os
import sys

_FROZEN = bool(getattr(sys, 'frozen', False))
_LOGGED = set()


def _roots():
    """Candidate base folders, most specific first, without duplicates."""
    roots = []
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        roots.append(meipass)
    if _FROZEN:
        exe_dir = os.path.dirname(sys.executable)
        roots.append(exe_dir)
        roots.append(os.path.join(exe_dir, '_internal'))
    roots.append(os.path.dirname(os.path.abspath(__file__)))
    roots.append(os.getcwd())
    seen, unique = set(), []
    for r in roots:
        key = os.path.normcase(os.path.abspath(r))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def log(message):
    """In the windowed exe print() goes nowhere, so keep a small log beside it."""
    if not _FROZEN or message in _LOGGED:
        return
    _LOGGED.add(message)
    try:
        log_path = os.path.join(os.path.dirname(sys.executable), 'asset_debug.log')
        with open(log_path, 'a', encoding='utf-8') as fh:
            fh.write(message + '\n')
    except Exception:
        pass


def asset_path(*parts):
    """Full path of assets/<parts...>, searching every known location.

    Returns the first existing file/folder.  If nothing exists, returns the path
    under the first root so callers' `os.path.isfile` checks fail cleanly."""
    roots = _roots()
    for root in roots:
        candidate = os.path.join(root, 'assets', *parts)
        if os.path.exists(candidate):
            return candidate
    missing = os.path.join(roots[0], 'assets', *parts)
    log('[assets] not found: assets/' + '/'.join(parts)
         + ' (searched: ' + ', '.join(roots) + ')')
    return missing


def audio_file(name):
    """assets/audio/<name>."""
    return asset_path('audio', name)


def audio_dir():
    """assets/audio folder."""
    return asset_path('audio')


def say(message):
    """print() the message and, in the exe, also record it in asset_debug.log."""
    try:
        print(message)
    except Exception:
        pass
    log(message)
