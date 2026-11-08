"""
Smoke tests for the openedx_search package and its Django app.
"""

from django.apps import apps

import openedx_search


def test_version_is_set():
    """The package exposes the version it was installed with."""
    assert openedx_search.__version__


def test_app_is_installed():
    """The Django app loads under its expected label."""
    app_config = apps.get_app_config("openedx_search")
    assert app_config.verbose_name == "Open edX Search"
