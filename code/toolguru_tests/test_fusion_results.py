"""CI test that validates Fusion integration test results are current.

The in-Fusion test runner saves results + a hash of the source files it
covers. This test recomputes the hash and checks that the saved results
match the current codebase. If they do, the integration test pass/fail
status is included in the CI report.

If the hash doesn't match (code changed since last manual test run),
this test fails with a message telling the developer to re-run the
Fusion integration tests.

NOTE FOR DEVELOPMENT: This test is EXPECTED TO FAIL during normal coding
sessions. You don't need to re-run the Fusion integration tests after
every change — that would be impractical. A hash mismatch here just means
the code has changed since the last manual test run. It should NOT block
development progress. However, before merging/pushing a final version,
remind the user to run "Run Tests" in Fusion and commit the updated
fusion_test_results.json.
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# hash_utils has no adsk dependency — safe to import without mocks. Imported
# from the prefixed package name (NOT bare `fusion_tests`) so other installed
# add-ins on the same `sys.path` can't shadow it. See ARCHITECTURE.md
# "Why prefix the test packages too?".
from toolguru_fusion_tests.hash_utils import compute_codebase_hash, get_results_path


class TestFusionIntegrationResults:
    """Validate that Fusion integration test results are current."""

    def _load_results(self):
        path = get_results_path()
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def test_results_file_exists(self):
        results = self._load_results()
        assert results is not None, (
            'Fusion integration test results not found. '
            'Run the "Run Tests" command in Fusion to generate them.'
        )

    def test_hash_matches_current_codebase(self):
        results = self._load_results()
        if results is None:
            assert False, 'No results file — run Fusion integration tests first.'

        current_hash = compute_codebase_hash()
        saved_hash = results.get('codebase_hash', '')

        assert current_hash == saved_hash, (
            f'Fusion integration tests are stale. '
            f'Code has changed since the last manual test run.\n'
            f'  Saved hash:   {saved_hash[:16]}...\n'
            f'  Current hash: {current_hash[:16]}...\n'
            f'Re-run the "Run Tests" command in Fusion to update.'
        )

    def test_all_fusion_tests_passed(self):
        results = self._load_results()
        if results is None:
            assert False, 'No results file — run Fusion integration tests first.'

        current_hash = compute_codebase_hash()
        if current_hash != results.get('codebase_hash', ''):
            assert False, 'Hash mismatch — re-run Fusion integration tests.'

        assert results.get('all_passed', False), (
            f'Fusion integration tests failed on last run:\n'
            f'  {results["passed"]}/{results["tests_run"]} passed, '
            f'{results["failed"]} failed, {results["errors"]} errors\n'
            f'  Run at: {results.get("timestamp", "unknown")}\n'
            f'Fix the failures and re-run in Fusion.'
        )

    def test_print_fusion_test_summary(self, capsys):
        """Print the integration test summary for inclusion in CI output."""
        results = self._load_results()
        if results is None:
            return

        current_hash = compute_codebase_hash()
        if current_hash != results.get('codebase_hash', ''):
            return

        print(f'\n--- Fusion Integration Test Results ---')
        print(f'Run at: {results.get("timestamp", "unknown")}')
        print(f'Tests:  {results["passed"]}/{results["tests_run"]} passed')
        if results['failed']:
            print(f'Failed: {results["failed"]}')
        if results['errors']:
            print(f'Errors: {results["errors"]}')

        cov = results.get('coverage')
        if cov:
            print(f'\nIntegration Test Coverage: {cov["percent_covered"]}% '
                  f'({cov["covered_lines"]}/{cov["num_statements"]} statements)')
            files = cov.get('files', {})
            if files:
                print(f'{"File":<30} {"Stmts":>6} {"Miss":>6} {"Cover":>6}')
                for name, fdata in sorted(files.items()):
                    print(f'{name:<30} {fdata["stmts"]:>6} {fdata["miss"]:>6} {fdata["cover"]:>5}%')

        print(f'Hash:   {results["codebase_hash"][:16]}...')
        print(f'--- End Fusion Results ---\n')
