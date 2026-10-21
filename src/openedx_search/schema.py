"""
Engine-neutral search schema model for openedx-search.

This module defines the declaration described in ADR 0002: one ``IndexSchema``
per use case, carrying both the document fields and the index settings. It is
plain Python (no Django, no engine client), so it can be imported from
application code, management commands and tests.

The model is deliberately strict. It rejects schemas that are ambiguous or that
cannot be represented by the supported engines. Options with no portable
meaning belong in ``extensions``, keyed by engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

__all__ = [
    "Capabilities",
    "CustomRank",
    "Direction",
    "Distinct",
    "Embedder",
    "EmbedderSource",
    "Facetable",
    "FacetSort",
    "Faceting",
    "Field",
    "FieldType",
    "IndexSchema",
    "LocalizedAttributes",
    "MatchMode",
    "Metric",
    "Pagination",
    "Ranking",
    "RankingRule",
    "Replica",
    "SchemaError",
    "Searchable",
    "Snippet",
    "Stem",
    "SynonymGroup",
    "Tokenization",
    "TypoTolerance",
    "VectorConfig",
    "VectorField",
]

INDEX_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
FIELD_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
FIELD_GLOB_PATTERN = re.compile(r"^[A-Za-z_*][A-Za-z0-9_.*]*$")
USE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class SchemaError(ValueError):
    """A schema or one of its parts is invalid."""


class FieldType(StrEnum):
    """
    Document field types shared by the supported engines.

    ``UNKNOWN`` is for fields parsed from engines that do not store types,
    such as Meilisearch and Algolia.
    """

    STRING = "string"
    INT32 = "int32"
    INT64 = "int64"
    FLOAT = "float"
    BOOL = "bool"
    DATETIME = "datetime"
    GEOPOINT = "geopoint"
    GEOPOLYGON = "geopolygon"
    OBJECT = "object"
    UNKNOWN = "unknown"


class MatchMode(StrEnum):
    """How a field name is interpreted."""

    LITERAL = "literal"
    GLOB = "glob"
    REGEX = "regex"


class RankingRule(StrEnum):
    """Engine-neutral ranking vocabulary."""

    TYPO = "typo"
    WORDS = "words"
    PROXIMITY = "proximity"
    ATTRIBUTE = "attribute"
    POSITION = "position"
    EXACTNESS = "exactness"
    CUSTOM = "custom"
    SORT = "sort"
    GEO = "geo"
    FILTERS = "filters"
    VECTOR = "vector"


class Direction(StrEnum):
    """Sort direction."""

    ASC = "asc"
    DESC = "desc"


class FacetSort(StrEnum):
    """How facet values are ordered."""

    ALPHA = "alpha"
    COUNT = "count"


class Metric(StrEnum):
    """Vector distance metric."""

    COSINE = "cosine"
    DOT = "dot"
    IP = "ip"
    EUCLIDEAN = "euclidean"


class EmbedderSource(StrEnum):
    """Supported embedding providers."""

    OPEN_AI = "openAi"
    HUGGING_FACE = "huggingFace"
    OLLAMA = "ollama"
    REST = "rest"
    USER_PROVIDED = "userProvided"
    COMPOSITE = "composite"


def _require(condition: bool, message: str) -> None:
    """Raise ``SchemaError`` when ``condition`` is false."""
    if not condition:
        raise SchemaError(message)


def _freeze(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return an immutable copy of a mapping."""
    return MappingProxyType(dict(value or {}))


def _enum(enum_type, value, label: str):
    """Coerce ``value`` to ``enum_type``, raising ``SchemaError`` if invalid."""
    try:
        return enum_type(value)
    except ValueError as exc:
        raise SchemaError(f"invalid {label}: {value!r}") from exc


def _validate_field_name(name: str, match: MatchMode) -> None:
    """Reject field names that the engines cannot address safely."""
    _require(isinstance(name, str) and bool(name), "field name must be a non-empty string")
    _require(
        not name.startswith(".") and not name.endswith(".") and ".." not in name,
        f"invalid field path {name!r}",
    )
    if match is MatchMode.REGEX:
        return
    pattern = FIELD_GLOB_PATTERN if match is MatchMode.GLOB else FIELD_NAME_PATTERN
    _require(bool(pattern.match(name)), f"invalid {match.value} field name {name!r}")


@dataclass(frozen=True, slots=True)
class Searchable:
    """Detailed searchable configuration for a field."""

    order: int | None = None
    weight: float | None = None
    unordered: bool = False
    prefix: bool = True
    infix: bool = False

    def __post_init__(self) -> None:
        """Validate the rank and weight bounds."""
        if self.order is not None:
            _require(self.order >= 1, "searchable order must be >= 1")
        if self.weight is not None:
            _require(self.weight > 0, "searchable weight must be > 0")


@dataclass(frozen=True, slots=True)
class Facetable:
    """Detailed facet configuration for a field."""

    searchable: bool = False


@dataclass(frozen=True, slots=True)
class Snippet:
    """Snippet configuration for a field."""

    length: int | None = None

    def __post_init__(self) -> None:
        """Validate the snippet length."""
        if self.length is not None:
            _require(self.length >= 1, "snippet length must be >= 1")


@dataclass(frozen=True, slots=True)
class Stem:
    """Stemming configuration for a field."""

    dictionary: str | None = None


@dataclass(frozen=True, slots=True)
class Capabilities:
    """
    Cross-engine capability flags for one field.

    ``facetable`` implies ``filterable`` in every supported engine, so setting
    it also sets ``filterable``.
    """

    searchable: bool | Searchable = False
    filterable: bool = False
    facetable: bool | Facetable = False
    sortable: bool = False
    retrievable: bool = True
    indexed: bool = True
    stored: bool = True
    highlight: bool = False
    snippet: bool | Snippet = False

    def __post_init__(self) -> None:
        """Validate the flag types and normalize facetability."""
        _require(
            isinstance(self.searchable, (bool, Searchable)),
            "searchable must be a bool or Searchable",
        )
        _require(
            isinstance(self.facetable, (bool, Facetable)),
            "facetable must be a bool or Facetable",
        )
        _require(
            isinstance(self.snippet, (bool, Snippet)),
            "snippet must be a bool or Snippet",
        )
        if self.facetable and not self.filterable:
            object.__setattr__(self, "filterable", True)


@dataclass(frozen=True, slots=True)
class Field:
    """
    A document field, or a pattern matching several fields.

    Nested fields use dot paths (``tags.level0``), which is how all supported
    engines address them.
    """

    name: str
    type: FieldType | str = FieldType.STRING
    match: MatchMode | str = MatchMode.LITERAL
    array: bool = False
    required: bool = False
    additional_properties: bool = False
    capabilities: Capabilities = field(default_factory=Capabilities)
    locale: str | None = None
    stem: bool | Stem = False
    truncate_len: int | None = None
    reference: str | None = None
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize the field."""
        field_type = _enum(FieldType, self.type, "field type")
        match_mode = _enum(MatchMode, self.match, "match mode")
        object.__setattr__(self, "type", field_type)
        object.__setattr__(self, "match", match_mode)

        _validate_field_name(self.name, match_mode)
        _require(
            isinstance(self.capabilities, Capabilities),
            "capabilities must be a Capabilities instance",
        )
        _require(isinstance(self.stem, (bool, Stem)), "stem must be a bool or Stem")
        if self.truncate_len is not None:
            _require(self.truncate_len >= 1, "truncate_len must be >= 1")
        if self.additional_properties:
            _require(field_type is FieldType.OBJECT, "additional_properties requires an object field")
        if self.capabilities.sortable:
            _require(field_type is not FieldType.OBJECT, f"object field {self.name!r} cannot be sortable")

        object.__setattr__(self, "extensions", _freeze(self.extensions))


@dataclass(frozen=True, slots=True)
class CustomRank:
    """One ``asc``/``desc`` tie-breaker."""

    field: str
    direction: Direction | str = Direction.DESC

    def __post_init__(self) -> None:
        """Normalize the direction."""
        object.__setattr__(self, "direction", _enum(Direction, self.direction, "direction"))


@dataclass(frozen=True, slots=True)
class Ranking:
    """Ordered relevance rules plus custom tie-breakers."""

    rules: tuple[RankingRule | str, ...] = ()
    custom: tuple[CustomRank, ...] = ()

    def __post_init__(self) -> None:
        """Normalize and validate the rule list."""
        rules = tuple(_enum(RankingRule, rule, "ranking rule") for rule in self.rules)
        _require(len(set(rules)) == len(rules), "ranking rules must be unique")
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "custom", tuple(self.custom))


@dataclass(frozen=True, slots=True)
class TypoTolerance:
    """Typo-tolerance configuration."""

    enabled: bool = True
    min_word_size_one_typo: int | None = None
    min_word_size_two_typos: int | None = None
    disable_on_words: tuple[str, ...] = ()
    disable_on_attributes: tuple[str, ...] = ()
    disable_on_numbers: bool = False
    on_numeric_tokens: bool = True

    def __post_init__(self) -> None:
        """Validate sizes and normalize sequences."""
        if self.min_word_size_one_typo is not None:
            _require(self.min_word_size_one_typo >= 1, "min_word_size_one_typo must be >= 1")
        if self.min_word_size_two_typos is not None:
            _require(self.min_word_size_two_typos >= 1, "min_word_size_two_typos must be >= 1")
        object.__setattr__(self, "disable_on_words", tuple(self.disable_on_words))
        object.__setattr__(self, "disable_on_attributes", tuple(self.disable_on_attributes))


@dataclass(frozen=True, slots=True)
class LocalizedAttributes:
    """Locale rules applied to matching attribute paths."""

    locales: tuple[str, ...]
    attribute_patterns: tuple[str, ...]

    def __post_init__(self) -> None:
        """Require at least one locale and one pattern."""
        _require(bool(self.locales), "localized attributes need at least one locale")
        _require(bool(self.attribute_patterns), "localized attributes need at least one pattern")
        object.__setattr__(self, "locales", tuple(self.locales))
        object.__setattr__(self, "attribute_patterns", tuple(self.attribute_patterns))


@dataclass(frozen=True, slots=True)
class Tokenization:
    """Word-splitting and token-normalization configuration."""

    separators: tuple[str, ...] = ()
    symbols_to_index: tuple[str, ...] = ()
    non_separators: tuple[str, ...] = ()
    dictionary: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    localized_attributes: tuple[LocalizedAttributes, ...] = ()
    custom_normalization: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize sequences and freeze the normalization map."""
        for name in (
            "separators",
            "symbols_to_index",
            "non_separators",
            "dictionary",
            "languages",
            "localized_attributes",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(
            self,
            "custom_normalization",
            MappingProxyType(
                {key: MappingProxyType(dict(value)) for key, value in self.custom_normalization.items()}
            ),
        )


@dataclass(frozen=True, slots=True)
class SynonymGroup:
    """A group of interchangeable terms."""

    terms: tuple[str, ...]
    synonyms: tuple[str, ...]
    one_way: bool = False
    placeholder: str | None = None

    def __post_init__(self) -> None:
        """Require at least one term and one synonym."""
        _require(bool(self.terms), "a synonym group needs at least one term")
        _require(bool(self.synonyms), "a synonym group needs at least one synonym")
        object.__setattr__(self, "terms", tuple(self.terms))
        object.__setattr__(self, "synonyms", tuple(self.synonyms))


@dataclass(frozen=True, slots=True)
class Faceting:
    """Facet value limits and ordering."""

    max_values_per_facet: int | None = None
    sort_by: Mapping[str, FacetSort | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the limit and normalize the sort map."""
        if self.max_values_per_facet is not None:
            _require(self.max_values_per_facet >= 1, "max_values_per_facet must be >= 1")
        object.__setattr__(
            self,
            "sort_by",
            MappingProxyType({key: _enum(FacetSort, value, "facet sort") for key, value in self.sort_by.items()}),
        )


@dataclass(frozen=True, slots=True)
class Pagination:
    """Result-pagination caps."""

    max_total_hits: int | None = None
    hits_per_page: int | None = None

    def __post_init__(self) -> None:
        """Validate the caps."""
        if self.max_total_hits is not None:
            _require(self.max_total_hits >= 1, "max_total_hits must be >= 1")
        if self.hits_per_page is not None:
            _require(self.hits_per_page >= 1, "hits_per_page must be >= 1")


@dataclass(frozen=True, slots=True)
class Distinct:
    """Deduplicate hits by a field value."""

    attribute: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class VectorField:
    """One embedding field of the index."""

    name: str
    dim: int | None = None
    metric: Metric | str = Metric.COSINE

    def __post_init__(self) -> None:
        """Validate the dimension and normalize the metric."""
        if self.dim is not None:
            _require(self.dim >= 1, "vector dim must be >= 1")
        object.__setattr__(self, "metric", _enum(Metric, self.metric, "metric"))


@dataclass(frozen=True, slots=True)
class Embedder:
    """Embedding provider configuration."""

    source: EmbedderSource | str
    model: str | None = None
    document_template: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize the source and freeze the options."""
        object.__setattr__(self, "source", _enum(EmbedderSource, self.source, "embedder source"))
        object.__setattr__(self, "options", _freeze(self.options))


@dataclass(frozen=True, slots=True)
class VectorConfig:
    """Vector search configuration for the index."""

    fields: tuple[VectorField, ...]
    embedders: Mapping[str, Embedder] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Require at least one vector field and freeze the embedder map."""
        _require(bool(self.fields), "vector configuration needs at least one field")
        object.__setattr__(self, "fields", tuple(self.fields))
        object.__setattr__(self, "embedders", MappingProxyType(dict(self.embedders)))


@dataclass(frozen=True, slots=True)
class Replica:
    """A derived index with different ranking."""

    name: str
    ranking: Ranking | None = None

    def __post_init__(self) -> None:
        """Validate the replica name."""
        _require(bool(INDEX_NAME_PATTERN.match(self.name)), f"invalid replica name {self.name!r}")


@dataclass(frozen=True, slots=True)
class IndexSchema:
    """
    A complete, engine-neutral index declaration.

    ``name`` identifies the schema, not necessarily the index it is mounted
    under: a use-case registration carries the logical index name, which lets
    two registrations share one schema.
    """

    name: str
    version: int = 1
    primary_key: str = "id"
    default_sort_field: str | None = None
    fields: tuple[Field, ...] = ()
    ranking: Ranking | None = None
    typo_tolerance: TypoTolerance | None = None
    tokenization: Tokenization | None = None
    stop_words: tuple[str, ...] = ()
    synonyms: tuple[SynonymGroup, ...] = ()
    faceting: Faceting | None = None
    pagination: Pagination | None = None
    distinct: Distinct | None = None
    vectors: VectorConfig | None = None
    replicas: tuple[Replica, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate cross-field invariants and freeze the collection members."""
        _require(bool(INDEX_NAME_PATTERN.match(self.name)), f"invalid schema name {self.name!r}")
        _require(self.version >= 1, "schema version must be >= 1")

        fields = tuple(self.fields)
        _require(bool(fields), "a schema needs at least one field")
        object.__setattr__(self, "fields", fields)

        by_name: dict[str, Field] = {}
        for entry in fields:
            _require(entry.name not in by_name, f"duplicate field name {entry.name!r}")
            by_name[entry.name] = entry

        _require(
            self.primary_key in by_name,
            f"primary key field {self.primary_key!r} is not declared",
        )

        if self.default_sort_field is not None:
            sort_field = by_name.get(self.default_sort_field)
            _require(sort_field is not None, f"default sort field {self.default_sort_field!r} is not declared")
            _require(sort_field.capabilities.sortable, "default sort field must be sortable")
            _require(
                sort_field.type in (FieldType.INT32, FieldType.INT64, FieldType.FLOAT, FieldType.DATETIME),
                "default sort field must be numeric or datetime",
            )

        if self.distinct is not None:
            _require(
                self.distinct.attribute in by_name,
                f"distinct attribute {self.distinct.attribute!r} is not declared",
            )

        if self.ranking is not None:
            for custom in self.ranking.custom:
                custom_field = by_name.get(custom.field)
                _require(custom_field is not None, f"custom ranking field {custom.field!r} is not declared")
                _require(custom_field.capabilities.sortable, "custom ranking fields must be sortable")

        if self.vectors is not None:
            for vector in self.vectors.fields:
                vector_field = by_name.get(vector.name)
                _require(vector_field is not None, f"vector field {vector.name!r} is not declared")
                _require(
                    vector_field.type is FieldType.FLOAT and vector_field.array,
                    "vector fields must be float arrays",
                )

        replica_names = [replica.name for replica in self.replicas]
        _require(len(set(replica_names)) == len(replica_names), "replica names must be unique")

        object.__setattr__(self, "stop_words", tuple(self.stop_words))
        object.__setattr__(self, "synonyms", tuple(self.synonyms))
        object.__setattr__(self, "replicas", tuple(self.replicas))
        object.__setattr__(self, "extensions", _freeze(self.extensions))

    def field(self, name: str) -> Field:
        """
        Return the field with this exact name.

        Raises ``KeyError`` when the field is not declared.
        """
        for entry in self.fields:
            if entry.name == name:
                return entry
        raise KeyError(name)
