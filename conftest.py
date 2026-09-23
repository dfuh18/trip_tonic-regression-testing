"""Puts this subtree on ``sys.path`` for pytest.

pytest inserts the directory of every ``conftest.py`` it collects, so this file
existing at the subtree root is what makes ``from src.config import settings``
resolve in ``tests/`` regardless of where pytest is invoked from. It holds no
fixtures on purpose.
"""


def pytest_configure(config):
    """Register the one marker this suite uses.

    slow is the traced dead-assert sweep (D80): it runs the whole suite
    under sys.settrace, which roughly quadruples the run, so it is excluded
    from the inner loop and belongs in CI. Registered here rather than in a
    pytest.ini because this subtree has no other pytest configuration and one
    marker does not earn a file.
    """
    config.addinivalue_line(
        "markers", "slow: excluded from the default run; see tests/test_no_dead_asserts.py"
    )
