"""
A search library for the Open edX platform, supporting Typesense and Meilisearch.
"""

from importlib.metadata import version as get_version

from .config import BackendConfig, BackendNotConfigured, BackendNotFound, get_backend_config
from .registry import (
    RegistrationError,
    UseCaseAlreadyRegistered,
    UseCaseNotRegistered,
    UseCaseRegistration,
    clear_registry,
    get_registration,
    iter_registrations,
    register_use_case,
    unregister_use_case,
)
from .schema import IndexSchema

__version__ = get_version(__package__)

__all__ = [
    "BackendConfig",
    "BackendNotConfigured",
    "BackendNotFound",
    "IndexSchema",
    "RegistrationError",
    "UseCaseAlreadyRegistered",
    "UseCaseNotRegistered",
    "UseCaseRegistration",
    "clear_registry",
    "get_backend_config",
    "get_registration",
    "iter_registrations",
    "register_use_case",
    "unregister_use_case",
]
