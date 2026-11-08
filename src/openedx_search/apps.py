"""
openedx_search Django application initialization.
"""

from django.apps import AppConfig


class OpenEdxSearchConfig(AppConfig):
    """
    Django app configuration for openedx_search.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "openedx_search"
    verbose_name = "Open edX Search"
