"""Codebase hashing for integration test validation.

Computes a deterministic hash of all Python source files under code/.
Used by both the in-Fusion test runner (to stamp results) and CI
(to verify results are current).
"""

import hashlib
import os

# Everything under code/ is covered — automatically picks up new
# directories, files, and removals without manual maintenance.
_CODE_DIR = os.path.join('code')

# Directories to exclude from hashing.
# Keep this in sync with `toolguru_commands/testRunner/entry.py:
# _compute_codebase_hash` — both must produce byte-identical digests.
_EXCLUDE_DIRS = {
    # Unit tests use mocks, not real API.
    os.path.join('code', 'toolguru_tests'),
    # Vendored coverage.py — installed locally via
    # `pip install coverage --target=code/lib/coverage_pkg`. Excluded so
    # the codebase hash stays stable across coverage.py version bumps.
    os.path.join('code', 'lib', 'coverage_pkg'),
}

# Repo root (two levels up from this file:
# code/toolguru_fusion_tests/ -> code/ -> repo).
_REPO_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..'))


def compute_codebase_hash():
    """Compute a SHA-256 hash of all .py files under code/ (excluding unit tests).

    Files are sorted by relative path for determinism. Both filenames and
    contents are hashed so that renames and additions/removals change the hash.
    Returns a hex digest string.
    """
    hasher = hashlib.sha256()
    files = []

    code_abs = os.path.join(_REPO_ROOT, _CODE_DIR)
    for dirpath, dirnames, filenames in os.walk(code_abs):
        rel_dir = os.path.relpath(dirpath, _REPO_ROOT)

        # Skip excluded directories
        if rel_dir in _EXCLUDE_DIRS or any(rel_dir.startswith(ex + os.sep) for ex in _EXCLUDE_DIRS):
            dirnames.clear()  # don't recurse
            continue

        # Skip __pycache__
        if '__pycache__' in rel_dir:
            continue

        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(rel_dir, filename))

    for rel_path in sorted(files):
        abs_path = os.path.join(_REPO_ROOT, rel_path)
        hasher.update(rel_path.encode('utf-8'))
        with open(abs_path, 'rb') as f:
            hasher.update(f.read())

    return hasher.hexdigest()


def get_results_path():
    """Return the path to the fusion test results JSON file."""
    return os.path.join(
        _REPO_ROOT, 'code', 'toolguru_tests', 'fusion_test_results.json',
    )
