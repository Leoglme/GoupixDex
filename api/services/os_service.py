"""Filesystem path helpers for resolving project-relative files."""

from pathlib import Path


def get_project_root() -> Path:
    """
    Return the repository root directory (parent of ``services/``).

    Returns:
        Absolute path to the project root.
    """
    return Path(__file__).resolve().parent.parent
