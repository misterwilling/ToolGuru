"""In-Fusion integration test runner.

Gated by `config.json: enable_tests`. When enabled, registers a "Run Tests"
button alongside the palette command in the add-in's toolbar panel.

Clicking the button:
  1. Loads every `test_*.py` under `code/toolguru_fusion_tests/` via
     explicit `importlib` (NOT `unittest.discover` — see note below).
  2. Runs them against the live Fusion API.
  3. Computes a SHA-256 hash of all source `.py` files under `code/`
     (excluding the unit-test package, which uses mocks).
  4. Writes a JSON results file to
     `code/toolguru_tests/fusion_test_results.json`, including a
     `coverage` block (per ARCHITECTURE.md §"Results file schema") when
     `coverage.py` is bundled at `code/lib/coverage_pkg/`.
  5. Shows a pass/fail summary in a message box and logs details to the
     Text Commands console.

## Two ways to trigger a run — both write the same artifact

The button and the headless `run_and_save()` function (see below) share the
exact same `_run_tests()` + `_save_results()` core, so they produce a
byte-identical `fusion_test_results.json` (codebase hash included). Use the
button for a manual run; call `run_and_save()` when driving Fusion
programmatically — most usefully through the Fusion MCP server's
`execute`/`script` tool, which lets an agent run the canonical suite without
clicking anything and read the results inline. See ARCHITECTURE.md
§"Layer 3" and CLAUDE.md §"Fusion MCP server".

CI (`code/toolguru_tests/test_fusion_results.py`) reads that JSON,
re-computes the hash, and fails the build if the hash drifted or any test
failed. The CI job-summary script also merges the `coverage` block with
the pytest-cov unit coverage to produce a combined per-file table.

## Coverage caveat

`coverage.py` traces line execution from the moment `cov.start()` is
called. Production modules are already imported at Fusion add-in startup
— hours before "Run Tests" is clicked — so their top-level `def`/`class`
lines never re-execute under tracing and appear missing. Function bodies
invoked by tests are recorded correctly. Treat file-level percentages as
a lower bound, not a literal score.

## Why explicit `importlib` instead of `unittest.discover`

`TestLoader.discover` interacts poorly with `top_level_dir` and
namespace-package handling across Fusion's bundled Python upgrades. When
the parent package name collides with another installed add-in's
(historically `fusion_tests` was a common collision), discover
silently produces opaque `_FailedTest` placeholders. Explicit
`importlib.util.spec_from_file_location` loads each test file by its
absolute path — bug-class-eliminated, and broken imports surface real
tracebacks instead of generic `_FailedTest` wrappers.

## Why the codebase hash is inlined here

The hash function MUST resolve paths from THIS file's `__file__`, not
through a `from toolguru_fusion_tests.hash_utils import …` round
trip. Other installed add-ins on `sys.path` may shadow that import — the
symptom is a hash that never matches CI no matter how many times you
re-run. See ARCHITECTURE.md "Why prefix the test packages too?".
"""

from __future__ import annotations

import adsk.core
import datetime
import glob
import hashlib
import importlib.util
import json
import os
import sys
import traceback
import unittest
from io import StringIO

from toolguru_lib.fusion360utils import event_utils as futil
from toolguru_lib.fusion360utils import general_utils as gutil
from toolguru_lib import config_utils

from ..ids import (
    COMPANY_NAME, ADDIN_NAME,
)


CMD_ID = f'{COMPANY_NAME}_{ADDIN_NAME}_runTests'
CMD_NAME = 'Run Tests'
CMD_DESC = f'Run {ADDIN_NAME} Fusion integration tests'

# The fusion-tests package directory — the parent the test files live in.
# Resolved relative to this file so a sibling add-in's package can't
# shadow it.
_FUSION_TESTS_PACKAGE = 'toolguru_fusion_tests'
_UNIT_TESTS_PACKAGE = 'toolguru_tests'

_local_handlers: list = []


class _ImportFailure:
    """Placeholder used in `result.errors` when a test file failed to
    import. Mirrors the (test, traceback) tuple shape unittest uses for
    real test failures, so the rest of the result-formatting code works
    without branching."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __str__(self) -> str:
        return f'{self._name} (import failed)'


def is_enabled() -> bool:
    try:
        cfg = config_utils.load_config()
    except Exception:
        return False
    return bool(cfg.get('enable_tests', False))


def start(panel: adsk.core.ToolbarPanel) -> None:
    if not is_enabled():
        return

    app = adsk.core.Application.get()
    ui = app.userInterface

    # Drop any stale command definition from a previous load before creating.
    existing = ui.commandDefinitions.itemById(CMD_ID)
    if existing:
        existing.deleteMe()

    cmd_def = ui.commandDefinitions.addButtonDefinition(
        CMD_ID, CMD_NAME, CMD_DESC,
    )
    futil.add_handler(cmd_def.commandCreated, _on_command_created)
    panel.controls.addCommand(cmd_def)


def stop() -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface
    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _on_command_created(args: adsk.core.CommandCreatedEventArgs) -> None:
    futil.add_handler(
        args.command.execute, _on_execute, local_handlers=_local_handlers,
    )
    args.command.isAutoExecute = True


def _on_execute(args: adsk.core.CommandEventArgs) -> None:
    try:
        results = run_and_save()
        _show_summary(results)
    except Exception:
        gutil.log(
            f'Test runner failed:\n{traceback.format_exc()}',
            force_console=True,
        )
        app = adsk.core.Application.get()
        if app:
            app.userInterface.messageBox(
                f'Test runner failed:\n{traceback.format_exc()}',
                f'{ADDIN_NAME} — Test Runner Error',
            )


def run_and_save() -> dict:
    """Run the full integration suite, write the canonical results JSON
    (codebase hash + coverage block included), and return the results dict.

    This is the UI-free entry point shared by the "Run Tests" button and any
    programmatic trigger — notably the Fusion MCP server's `execute` /
    `script` tool, which lets an agent run the suite headlessly against the
    live session:

        from toolguru_commands.testRunner.entry import run_and_save

        def run(_context):
            r = run_and_save()
            print(f"run={r['tests_run']} passed={r['passed']} "
                  f"failed={r['failed']} errors={r['errors']}")
            print("hash", r['codebase_hash'])
            for f in r['failures'] + r['error_details']:
                print(f['name']); print(f['traceback'])

    Because it goes through the exact same `_run_tests()` + `_save_results()`
    path as the button, the `fusion_test_results.json` it writes — codebase
    hash and all — is byte-for-byte what CI validates. An MCP-triggered run
    satisfies the CI hash gate identically to a button click; there is no
    second-class path. It does NOT touch the UI: callers that want a message
    box call `_show_summary()` themselves (the button does, via `_on_execute`).

    NOT gated by `enable_tests` — that flag only controls whether the toolbar
    button is registered, not whether the suite can be invoked
    programmatically. The hot-reload caveat still applies: `_run_tests()`
    re-imports the test files on every call, but production modules under test
    are NOT purged, so a run after editing production source exercises the
    STALE in-memory code until the add-in is restarted (Stop → Run in Scripts
    and Add-Ins). Restart, then trigger the run, to test fresh source.
    """
    results, _log_output = _run_tests()
    _save_results(results)
    return results


def _run_tests() -> tuple[dict, str]:
    """Load and run every `test_*.py` under the fusion-tests package."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    # code/<prefix>_commands/testRunner/entry.py  →  code/
    code_dir = os.path.abspath(os.path.join(this_dir, '..', '..'))
    fusion_tests_dir = os.path.join(code_dir, _FUSION_TESTS_PACKAGE)

    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)

    # Purge previously-imported test modules so edits to test files take
    # effect on the next click without requiring a full Fusion restart.
    for name in [k for k in sys.modules
                 if k == _FUSION_TESTS_PACKAGE
                 or k.startswith(_FUSION_TESTS_PACKAGE + '.')]:
        del sys.modules[name]

    # Import the parent package first. Manually loading children via
    # `spec_from_file_location` and stashing them under
    # `sys.modules['<pkg>.test_X']` only works if the parent is already
    # in sys.modules — otherwise relative imports inside the test file
    # (and importlib's parent-attribute binding) fall over.
    importlib.import_module(_FUSION_TESTS_PACKAGE)

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    import_errors: list[tuple[str, str]] = []

    test_files = sorted(glob.glob(os.path.join(fusion_tests_dir, 'test_*.py')))
    for path in test_files:
        leaf = os.path.splitext(os.path.basename(path))[0]
        mod_name = f'{_FUSION_TESTS_PACKAGE}.{leaf}'
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(
                    f'spec_from_file_location returned None for {path}'
                )
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            # Bind the child as an attribute of the parent so dotted
            # references (`<pkg>.test_X` from anywhere else) resolve.
            setattr(sys.modules[_FUSION_TESTS_PACKAGE], leaf, module)
            suite.addTests(loader.loadTestsFromModule(module))
        except Exception:
            # Capture the real traceback — discover used to swallow these.
            import_errors.append((mod_name, traceback.format_exc()))
            sys.modules.pop(mod_name, None)

    stream = StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)

    # Bracket the actual test run in coverage tracing so the test
    # invocations of production code are recorded. Coverage is best-effort:
    # if the package isn't installed in the bundled `code/lib/coverage_pkg/`,
    # the rest of the run still succeeds and the `coverage` block is
    # omitted from results.
    repo_root = os.path.abspath(os.path.join(this_dir, '..', '..', '..'))
    cov = _try_start_coverage(code_dir, repo_root)
    try:
        result = runner.run(suite)
    finally:
        coverage_block = _finalize_coverage(cov, code_dir, repo_root)
    log_output = stream.getvalue()

    # Surface import failures as test errors so the JSON results and the
    # summary message box reflect them — otherwise a broken test file
    # would silently disappear from the run.
    for mod_name, tb in import_errors:
        log_output += f'\nERROR importing {mod_name}:\n{tb}\n'
        result.errors.append((_ImportFailure(mod_name), tb))
        result.testsRun += 1

    passed = result.testsRun - len(result.failures) - len(result.errors)

    results = {
        'tests_run': result.testsRun,
        'passed': passed,
        'failed': len(result.failures),
        'errors': len(result.errors),
        'all_passed': result.wasSuccessful(),
        'timestamp': datetime.datetime.now().isoformat(timespec='seconds'),
        'codebase_hash': _compute_codebase_hash(),
        'failures': [
            {'name': str(test), 'traceback': tb}
            for test, tb in result.failures
        ],
        'error_details': [
            {'name': str(test), 'traceback': tb}
            for test, tb in result.errors
        ],
    }
    if coverage_block is not None:
        results['coverage'] = coverage_block

    gutil.log('--- Fusion Integration Test Results ---', force_console=True)
    gutil.log(log_output, force_console=True)
    gutil.log('--- End ---', force_console=True)

    return results, log_output


def _compute_codebase_hash() -> str:
    """SHA-256 of all `.py` files under `code/` (excluding the unit-test
    package). Resolves paths from THIS file's `__file__`, NOT via
    `from toolguru_fusion_tests.hash_utils import …` — that import
    can be silently shadowed by another installed add-in's `fusion_tests`
    package on `sys.path`, leaving the testRunner stamping a hash that
    refers to a different add-in's source tree. (This is exactly the bug
    that prompted the prefix-the-test-packages rule; see ARCHITECTURE.md.)

    Mirrors `code/toolguru_fusion_tests/hash_utils.py` so CI's
    independent recomputation produces an identical digest.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    # code/<prefix>_commands/testRunner/entry.py  →  repo root
    repo_root = os.path.abspath(os.path.join(this_dir, '..', '..', '..'))
    code_dir = os.path.join(repo_root, 'code')
    excluded = {
        os.path.join('code', _UNIT_TESTS_PACKAGE),
        # Vendored coverage.py — installed locally via
        # `pip install coverage --target=code/lib/coverage_pkg`. Excluding
        # keeps the codebase hash stable across coverage.py version bumps.
        os.path.join('code', 'lib', 'coverage_pkg'),
    }

    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(code_dir):
        rel_dir = os.path.relpath(dirpath, repo_root)
        if rel_dir in excluded or any(
            rel_dir.startswith(e + os.sep) for e in excluded
        ):
            dirnames.clear()
            continue
        if '__pycache__' in rel_dir:
            continue
        for fn in filenames:
            if fn.endswith('.py'):
                files.append(os.path.join(rel_dir, fn))

    hasher = hashlib.sha256()
    for rel in sorted(files):
        hasher.update(rel.encode('utf-8'))
        with open(os.path.join(repo_root, rel), 'rb') as f:
            hasher.update(f.read())
    return hasher.hexdigest()


def _try_start_coverage(code_dir: str, repo_root: str):
    """Best-effort start of `coverage.py` measurement around the test run.

    `coverage` is shipped as a vendored package at `code/lib/coverage_pkg/`
    (gitignored — install via
    `pip install coverage --target=code/lib/coverage_pkg`). If the package
    isn't present we return None and the run continues without coverage —
    the rest of the testRunner doesn't care.
    """
    coverage_pkg = os.path.join(code_dir, 'lib', 'coverage_pkg')
    if os.path.isdir(coverage_pkg) and coverage_pkg not in sys.path:
        sys.path.insert(0, coverage_pkg)
    try:
        import coverage  # type: ignore  # noqa: PLC0415
    except ImportError:
        gutil.log(
            '[testRunner] coverage.py not bundled — skipping coverage. '
            'Install via `pip install coverage --target=code/lib/coverage_pkg` '
            'to enable.',
            force_console=True,
        )
        return None
    except Exception:
        gutil.log(
            f'[testRunner] coverage import failed:\n{traceback.format_exc()}',
            force_console=True,
        )
        return None

    try:
        results_dir = os.path.join(repo_root, 'code', _UNIT_TESTS_PACKAGE)
        cov = coverage.Coverage(
            data_file=os.path.join(results_dir, '.coverage.fusion'),
            source=[
                os.path.join(code_dir, 'toolguru_lib'),
                os.path.join(code_dir, 'toolguru_commands'),
            ],
            # Exclude the testRunner itself (no point measuring the runner)
            # and the vendored coverage package (would self-trace).
            omit=[
                os.path.join(code_dir, 'toolguru_commands', 'testRunner', '*'),
                os.path.join(code_dir, 'lib', 'coverage_pkg', '*'),
            ],
        )
        cov.start()
        gutil.log('[testRunner] coverage tracing started', force_console=True)
        return cov
    except Exception:
        gutil.log(
            f'[testRunner] coverage start failed:\n{traceback.format_exc()}',
            force_console=True,
        )
        return None


def _finalize_coverage(cov, code_dir: str, repo_root: str) -> dict | None:
    """Stop coverage, build the JSON block per ARCHITECTURE.md schema.

    Returns a dict shaped like:
      {
        'percent_covered': float,
        'covered_lines': int,
        'num_statements': int,
        'missing_lines': int,
        'files': { '<basename>': { 'stmts': int, 'miss': int, 'cover': float } }
      }
    or None if coverage wasn't started or finalization failed. Per-file keys
    use basenames so the CI workflow's basename merge against pytest-cov's
    `coverage-unit.json` finds matching entries.

    *Caveat*: production modules are imported when Fusion loads the add-in,
    long before `Run Tests` is clicked. Top-level `def`/`class` lines won't
    re-execute under tracing and will appear as missing. Function bodies
    invoked by tests are recorded correctly. Treat the file-level numbers
    as a lower bound.
    """
    if cov is None:
        return None

    try:
        cov.stop()
        cov.save()
    except Exception:
        gutil.log(
            f'[testRunner] coverage stop/save failed:\n{traceback.format_exc()}',
            force_console=True,
        )
        return None

    try:
        results_dir = os.path.join(repo_root, 'code', _UNIT_TESTS_PACKAGE)
        report_path = os.path.join(results_dir, 'fusion_coverage.json')
        cov.json_report(outfile=report_path)
        with open(report_path) as f:
            cov_json = json.load(f)
    except Exception:
        gutil.log(
            f'[testRunner] coverage report failed:\n{traceback.format_exc()}',
            force_console=True,
        )
        return None

    totals = cov_json.get('totals', {})
    files_block: dict[str, dict] = {}
    for fpath, fdata in cov_json.get('files', {}).items():
        s = fdata.get('summary', {})
        files_block[os.path.basename(fpath)] = {
            'stmts': s.get('num_statements', 0),
            'miss': s.get('missing_lines', 0),
            'cover': round(s.get('percent_covered', 0), 1),
        }

    return {
        'percent_covered': round(totals.get('percent_covered', 0), 1),
        'covered_lines': totals.get('covered_lines', 0),
        'num_statements': totals.get('num_statements', 0),
        'missing_lines': totals.get('missing_lines', 0),
        'files': files_block,
    }


def _save_results(results: dict) -> None:
    """Write the results JSON. Path is computed from THIS file's `__file__`
    (NOT via `<pkg>.hash_utils.get_results_path` — same shadowing risk
    as the hash function). Logs the destination on success and the full
    traceback on failure so a silent save miss can't leave the on-disk
    file stale."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    # code/<prefix>_commands/testRunner/entry.py  →  repo root
    repo_root = os.path.abspath(os.path.join(this_dir, '..', '..', '..'))
    path = os.path.join(
        repo_root, 'code', _UNIT_TESTS_PACKAGE, 'fusion_test_results.json',
    )
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(results, f, indent=2)
        gutil.log(f'[testRunner] results written → {path}', force_console=True)
    except Exception:
        gutil.log(
            f'[testRunner] FAILED to write results to {path}:\n'
            f'{traceback.format_exc()}',
            force_console=True,
        )
        raise


def _show_summary(results: dict) -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface

    header = (
        'All tests passed' if results['all_passed'] else 'Test failures'
    )
    title = f'{ADDIN_NAME} — {header}'

    summary = (
        f'Tests run: {results["tests_run"]}\n'
        f'Passed:    {results["passed"]}\n'
        f'Failed:    {results["failed"]}\n'
        f'Errors:    {results["errors"]}\n'
        f'Hash:      {results["codebase_hash"][:16]}...\n'
        f'\n'
        f'Results written to '
        f'code/{_UNIT_TESTS_PACKAGE}/fusion_test_results.json.\n'
        f'Full log: View → Text Commands.'
    )

    if not results['all_passed']:
        # Trim to keep message box reasonable — full tracebacks live in
        # the results JSON and the Text Commands log.
        first_failures = (
            results['failures'][:3] + results['error_details'][:3]
        )
        if first_failures:
            summary += '\n\nFirst failures:'
            for entry in first_failures:
                first_line = entry['traceback'].strip().splitlines()
                snippet = first_line[-1] if first_line else ''
                summary += f'\n  • {entry["name"]}: {snippet[:80]}'

    ui.messageBox(summary, title)
