"""The dates stored for a scanned program, against a made-up hub file.

Fusion reports a file's `dateCreated` as the date of its latest version, so
"first used" has to come from the oldest version instead.
"""

from types import SimpleNamespace

import pytest

from toolguru_tests.mock_adsk import setup_adsk_modules

setup_adsk_modules()

from toolguru_lib import extract
from toolguru_lib.records import DocumentRecord, ScanError
from toolguru_tests.mock_adsk import MockCollection


def make_version(number: int, saved: int) -> SimpleNamespace:
    return SimpleNamespace(versionNumber=number, dateCreated=saved)


def make_file(version_dates: dict[int, int], listed: list[int]) -> SimpleNamespace:
    """A hub file as Fusion reports it: its own dates are those of the latest
    version. `listed` is the order Fusion returns the versions in."""
    latest = max(version_dates)
    return SimpleNamespace(
        id='file-1', name='Program', versionNumber=latest,
        parentProject=SimpleNamespace(name='Project'),
        dateCreated=version_dates[latest], dateModified=version_dates[latest],
        versions=MockCollection(
            [make_version(n, version_dates[n]) for n in listed]))


def test_first_used_is_the_first_version_and_last_used_the_latest(monkeypatch):
    monkeypatch.setattr(extract.time, 'time', lambda: 5000.9)
    data_file = make_file({1: 1000, 2: 2000, 3: 3000}, listed=[3, 1, 2])

    assert extract.document_record(SimpleNamespace(dataFile=data_file)) == (
        DocumentRecord(file_id='file-1', version=3, name='Program',
                       project='Project', date_created=1000,
                       date_modified=3000, scanned_at=5000, scan_level=2))


def test_the_oldest_version_is_found_wherever_fusion_lists_it():
    dates = {n: n * 100 for n in range(1, 13)}
    as_text = sorted(dates, key=str, reverse=True)   # 9, 8, ... 12, 11, 10, 1

    assert extract.first_saved(make_file(dates, listed=as_text)) == 100


def test_a_file_saved_once_keeps_its_own_date():
    assert extract.first_saved(make_file({1: 500}, listed=[1])) == 500


def test_a_file_whose_versions_are_not_listed_keeps_its_own_date():
    assert extract.first_saved(make_file({4: 4000}, listed=[])) == 4000


def test_an_unsaved_document_is_refused():
    with pytest.raises(ScanError, match='Save this document to your hub'):
        extract.document_record(SimpleNamespace(dataFile=None))
