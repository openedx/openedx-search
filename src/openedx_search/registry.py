"""
Use-case registration API.

ADR 0002, Decision 1: every search use case registers itself, declaring its
logical index, schema and the document types it routes there. The registration
is engine-neutral; the deployment chooses the backend.

The registry is process-local and thread-safe. Registrations normally happen at
import time, and ``replace=True`` is available for development reloads and
tests.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .schema import INDEX_NAME_PATTERN, USE_CASE_PATTERN, IndexSchema

__all__ = [
    "RegistrationError",
    "UseCaseAlreadyRegistered",
    "UseCaseNotRegistered",
    "UseCaseRegistration",
    "clear_registry",
    "get_registration",
    "iter_registrations",
    "register_use_case",
    "unregister_use_case",
]


class RegistrationError(ValueError):
    """A use-case registration is invalid."""


class UseCaseAlreadyRegistered(RegistrationError):
    """The use case already has a registration."""


class UseCaseNotRegistered(LookupError):
    """There is no registration for the requested use case."""


def _require(condition: bool, message: str) -> None:
    """Raise ``RegistrationError`` when ``condition`` is false."""
    if not condition:
        raise RegistrationError(message)


@dataclass(frozen=True, slots=True)
class UseCaseRegistration:
    """
    One search surface registered with the library.

    ``index`` is a logical name. A backend maps it to its own namespace, such as
    a Meilisearch index UID or a Typesense collection plus its alias.
    """

    use_case: str
    index: str
    schema: IndexSchema
    document_types: tuple[str, ...]
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the registration and freeze its collections."""
        _require(
            isinstance(self.use_case, str) and bool(USE_CASE_PATTERN.match(self.use_case)),
            f"invalid use case name {self.use_case!r}",
        )
        _require(
            isinstance(self.index, str) and bool(INDEX_NAME_PATTERN.match(self.index)),
            f"invalid index name {self.index!r}",
        )
        _require(isinstance(self.schema, IndexSchema), "schema must be an IndexSchema")

        document_types = tuple(self.document_types)
        _require(bool(document_types), "a registration needs at least one document type")
        _require(len(set(document_types)) == len(document_types), "document types must be unique")
        _require(
            all(isinstance(item, str) and bool(item) for item in document_types),
            "document types must be non-empty strings",
        )

        object.__setattr__(self, "document_types", document_types)
        object.__setattr__(self, "extensions", MappingProxyType(dict(self.extensions)))


_lock = threading.RLock()
_registrations: dict[str, UseCaseRegistration] = {}


def register_use_case(
    registration: UseCaseRegistration,
    *,
    replace: bool = False,
) -> UseCaseRegistration:
    """
    Register a use case and return it.

    Raises ``UseCaseAlreadyRegistered`` when the use case is already present,
    unless ``replace`` is true.
    """
    _require(isinstance(registration, UseCaseRegistration), "registration must be a UseCaseRegistration")
    with _lock:
        if registration.use_case in _registrations and not replace:
            raise UseCaseAlreadyRegistered(f"use case {registration.use_case!r} is already registered")
        _registrations[registration.use_case] = registration
    return registration


def get_registration(use_case: str) -> UseCaseRegistration:
    """
    Return the registration for ``use_case``.

    Raises ``UseCaseNotRegistered`` when there is none.
    """
    with _lock:
        try:
            return _registrations[use_case]
        except KeyError:
            raise UseCaseNotRegistered(f"no registration for use case {use_case!r}") from None


def iter_registrations() -> tuple[UseCaseRegistration, ...]:
    """Return every registration, ordered by use case name."""
    with _lock:
        return tuple(_registrations[name] for name in sorted(_registrations))


def unregister_use_case(use_case: str) -> None:
    """
    Remove a registration.

    Raises ``UseCaseNotRegistered`` when there is none.
    """
    with _lock:
        try:
            del _registrations[use_case]
        except KeyError:
            raise UseCaseNotRegistered(f"no registration for use case {use_case!r}") from None


def clear_registry() -> None:
    """Remove every registration. Intended for tests and process shutdown."""
    with _lock:
        _registrations.clear()
