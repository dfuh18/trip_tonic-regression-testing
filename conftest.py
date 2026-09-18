"""Puts this subtree on ``sys.path`` for pytest.

pytest inserts the directory of every ``conftest.py`` it collects, so this file
existing at the subtree root is what makes ``from src.config import settings``
resolve in ``tests/`` regardless of where pytest is invoked from. It holds no
fixtures on purpose.
"""
