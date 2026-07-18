"""Session-wide collection hooks.

Cross-test isolation ordering: a handful of tests mutate *process-global* state that other
tests rely on staying stable, in ways a per-test fixture can't undo. Rather than skip or
weaken those tests, they are pinned to run strictly last so nothing scheduled afterward can
observe the mutation — this preserves full parallelism for the rest of the suite instead of
serializing everything.
"""

from __future__ import annotations

import pytest

# Test ids (substring match against nodeid) that must run after everything else. Currently:
# TestRestartEquivalentRebootstrap calls importlib.reload(src.infrastructure.app_bootstrap),
# which replaces that module's top-level function objects (e.g. runtime_catalogs_dependency,
# module_registry_dependency) in place. Router modules already imported at collection time
# hold FastAPI `Depends(...)` bound to the pre-reload objects, so any other test on the same
# xdist worker that re-imports app_bootstrap fresh (to build `dependency_overrides`) after
# this one has run would get a *different* object identity than the router's — the override
# then silently misses and the real (uninstalled-registry) dependency runs instead. Pytest's
# default `--dist=load` xdist scheduler dispatches collected items in collection order to
# whichever worker next asks for work, so a test placed last in the full collected list is
# guaranteed to be the last test executed in the entire session, on any worker — no other
# test can run afterward to observe the mutation.
_RUN_LAST_SUBSTRINGS = (
    "tests/cli/test_arch_import_guidance.py::TestRestartEquivalentRebootstrap",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    run_last = [item for item in items if any(needle in item.nodeid for needle in _RUN_LAST_SUBSTRINGS)]
    if not run_last:
        return
    remaining = [item for item in items if item not in run_last]
    items[:] = remaining + run_last


@pytest.fixture(autouse=True)
def _reset_installed_mutation_executor():
    """No test may leak an installed AuthorizedMutationExecutor to its successors.

    Tests that install one (over their own tmp roots and mode flags) would
    otherwise poison later tests on the same worker with foreign-root snapshots —
    every later REST/MCP write then 403s as target_not_engagement_root. Resetting
    after every test restores the dynamic workspace-default composition.
    """
    yield
    from src.infrastructure.write.mutation_executor_registry import _reset_executor_for_test

    _reset_executor_for_test()
