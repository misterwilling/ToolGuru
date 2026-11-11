"""The codebase hash must be the same on Windows (where Fusion stamps it) and
on CI's Linux runner (where it is re-checked), and the two copies of the
algorithm must agree."""

import hashlib
from pathlib import Path

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_commands.testRunner import entry as test_runner
from toolguru_fusion_tests import hash_utils


def _write_tree(root: Path, newline: bytes) -> None:
    (root / 'code' / 'pkg' / 'sub').mkdir(parents=True)
    (root / 'code' / 'pkg' / 'a.py').write_bytes(b'x = 1' + newline)
    (root / 'code' / 'pkg' / 'sub' / 'b.py').write_bytes(b'y = 2' + newline)


def _expected_digest() -> str:
    hasher = hashlib.sha256()
    hasher.update(b'code/pkg/a.py')
    hasher.update(b'x = 1\n')
    hasher.update(b'code/pkg/sub/b.py')
    hasher.update(b'y = 2\n')
    return hasher.hexdigest()


def test_hash_uses_forward_slash_paths_and_lf_contents(tmp_path, monkeypatch):
    _write_tree(tmp_path, b'\n')
    monkeypatch.setattr(hash_utils, '_REPO_ROOT', str(tmp_path))
    assert hash_utils.compute_codebase_hash() == _expected_digest()


def test_crlf_checkout_hashes_the_same_as_lf_checkout(tmp_path, monkeypatch):
    _write_tree(tmp_path, b'\r\n')
    monkeypatch.setattr(hash_utils, '_REPO_ROOT', str(tmp_path))
    assert hash_utils.compute_codebase_hash() == _expected_digest()


def test_unit_test_package_is_left_out_of_the_hash(tmp_path, monkeypatch):
    _write_tree(tmp_path, b'\n')
    (tmp_path / 'code' / 'toolguru_tests').mkdir()
    (tmp_path / 'code' / 'toolguru_tests' / 't.py').write_bytes(b'z = 3\n')
    monkeypatch.setattr(hash_utils, '_REPO_ROOT', str(tmp_path))
    assert hash_utils.compute_codebase_hash() == _expected_digest()


def test_test_runner_copy_agrees_with_hash_utils():
    assert test_runner._compute_codebase_hash() == hash_utils.compute_codebase_hash()
