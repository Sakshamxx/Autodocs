"""The environment works."""

import autodocs


def test_package_imports():
    """The package can be imported."""
    assert autodocs.__doc__
