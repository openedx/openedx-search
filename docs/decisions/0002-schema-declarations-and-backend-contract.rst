0002 Use-Case Schema Declarations and Backend Contract
#######################################################

Status
******

**Draft** (for upstream discussion)

Context
*******

`0001-purpose-of-this-repo.rst`_ establishes ``openedx-search`` as the single
search library for the platform and decides that use cases register themselves,
each declaring a document schema, index settings and a query shape. It also
fixes the engine scope: Typesense and Meilisearch are implemented, Algolia stays
adoptable, and Elasticsearch and OpenSearch are out of scope.

That ADR deliberately leaves the concrete shape of a declaration open. Without
settling it, a backend cannot be written: everything that talks to an engine has
to know what a document is, how settings reach the engine, and which engine a
use case runs on.

This ADR settles those three questions. It does not revisit the engine scope or
the registration model from ADR 0001.

The first adopter is ``content/search`` in ``openedx-platform``. Its declaration
is currently split between ``index_config.py`` (settings) and ``documents.py``
(document shape), with the exact document shape pinned by
``tests/test_documents.py``. Studio courseware and library content are separate
use cases with different document shapes. They share the index settings but not
the schema, which is why the declaration model separates the two.

An initial contribution (``openedx/openedx-search#3``) and its benchmark
(``openedx/openedx-search#4``) take a narrower route: a flat, string-only
backend contract. They are recorded under Alternatives Considered rather than
treated as rejected, so the trade-off can be discussed upstream.

Decision
********

1. One schema model
===================

There is a single authored declaration type, ``IndexSchema``. It contains:

* identity: ``name``, ``primary_key`` and a ``version``;
* ``fields``: one entry per document field or field path, with a ``type``
  (``string``, ``int32``, ``int64``, ``float``, ``bool``, ``datetime``,
  ``geopoint``, ``geopolygon``, ``object``), whether it is an ``array`` or a
  free-form object, whether it is ``required``, and its capabilities;
* capabilities, as seven independent flags: ``searchable``, ``filterable``,
  ``facetable``, ``sortable``, ``retrievable``, ``indexed`` and ``stored``,
  plus ``order``/``weight`` for searchable fields;
* index settings: ``ranking``, ``typo_tolerance``, ``tokenization``,
  ``stop_words``, ``synonyms``, ``faceting``, ``pagination``, ``distinct``,
  ``vectors`` and ``replicas``;
* ``extensions``: a per-engine escape hatch for options that have no portable
  meaning.

Document schema and index settings share one object on purpose. They are
coupled in every engine: a field's ``facetable`` capability becomes
``facet: true`` on Typesense and an entry in Meilisearch's
``filterableAttributes``; ``sortable`` becomes a per-field ``sort`` or a
replica. Two authored models would create two places to keep in sync, and every
capability would need a rule to cross between them.

The registration still declares a document schema, index settings and a query
shape, as ADR 0001 requires. It is the storage and validation that are shared,
not the concepts. Accessors may expose the document schema and the settings
separately.

2. Registrations are engine-neutral
===================================

A registration names the use case, the logical index, the schema, the document
types it routes to that index, and its query shape. It has **no backend field**.

::

    UseCaseRegistration
      use_case        str
      index           str            logical index name
      schema          IndexSchema
      document_types  list[str]      which documents this registration indexes
      query_shape     QueryShape     filters, facets, sort, defaults

``index`` is a logical name. A backend maps it to its own namespace: a
Meilisearch index UID, or a Typesense collection plus the alias used for
rebuilds. Prefixes and aliases are backend concerns.

Studio courseware and library content are separate registrations with separate
schemas. The course schema covers ``course_block`` documents; the library schema
is the union of ``library_block``, ``library_container`` and ``collection``
documents. They differ in ``index``, ``document_types`` and ``schema``, which
keeps the use-case boundary that ADR 0001 Decision 1 asks for.

Registrations are loaded by the consumer, from its own ``AppConfig.ready()``.
The library does not scan packages or import registration modules on its own.
That keeps import side effects out of the library and lets each consumer own its
startup cost. ``register_use_case(..., replace=True)`` covers development reloads
and repeated ``ready()`` calls in tests.

3. Engine selection is deployment configuration
===============================================

The engines are configured once per deployment, in the deployment's config file.
The library ships no default engine: if the configuration does not name one,
resolution raises rather than picking an engine.

::

    OPENEDX_SEARCH_BACKENDS = {
        "default": {"engine": "meilisearch", "options": {...}},
    }
    OPENEDX_SEARCH_DEFAULT_BACKEND = "default"
    OPENEDX_SEARCH_USE_CASE_BACKENDS = {"forum": "default"}   # optional

Setting names are illustrative; the decision is the location and the resolution
order, not the spelling.

For each use case the library resolves the backend in this order:

#. the per-use-case override, if configured;
#. otherwise the deployment default;
#. otherwise raise.

One backend per deployment is the expected case. Running more than one is
allowed, because there is no reason to forbid it, but it is not the target
setup. Registrations do not change when it happens; only the resolution does.

This answers ADR 0001's open question about the default engine at deploy time
rather than in code. Neither engine is privileged by the library.

4. One model, many renderers
============================

Backends render ``IndexSchema`` into their own payload in ``configure(schema)``:
a Meilisearch settings object, a Typesense collection schema, or an Algolia
settings object. There is no second authored schema type between the
declaration and the engine.

A derived projection may exist internally for convenience, but it must not
become an authored type. A second model would either grow until it duplicates
``IndexSchema`` or stay narrow and cap which use cases can be supported, and in
the meantime every new capability would need a rule to cross the boundary.
Typesense, Meilisearch and Algolia are the same shape of engine, so their
differences are encoding differences, not model differences.

5. Backends declare capabilities and validate
=============================================

Every backend implements a small protocol:

::

    capabilities()                    -> set of feature flags
    validate(schema)                  -> raises UnsupportedSchema
    configure(schema)                 -> renders and applies settings
    upsert(documents)                 -> WriteReceipt
    search(query)                     -> SearchResult
    mint_credential(scope, expires)   -> str
    reconcile(schema)                 -> ReconcileResult

Capability flags cover the parts engines differ on, for example
``nested_fields``, ``sortable``, ``distinct``, ``highlight``, ``synonyms``,
``vectors``, ``scoped_credentials`` and ``index_reconciliation``.

``validate(schema)`` is called when a use case is registered and before settings
are applied. If a use case needs something the configured backend cannot do, it
must fail there, with a message naming the unsupported parts. Silently dropping
a capability is not acceptable, because a dropped filter or a missing sort
changes results.

Capabilities are the narrow, stable part of the backend contract. That is the
thing worth freezing, not a parallel schema.

6. Document validation is shared
================================

The library validates documents against ``IndexSchema`` before handing them to a
backend: field names, types, arrays, required fields, free-form objects, and the
portable subset of the document id.

Backends do not reimplement document validation. Engine-specific limits, such as
a maximum batch size or an id charset, are declared as capabilities and applied
by the shared validator, so every engine rejects the same bad document for the
same reason.

7. Query contracts are separate from the schema
===============================================

Runtime queries use a small, engine-neutral contract, distinct from the schema:

* ``FilterTerm``: exact match against one field, with a set of allowed values;
  terms are combined with AND.
* ``SearchQuery``: text, filter terms, page and page size.
* ``SearchResult``: documents, total, and whether the total is exact.
* ``WriteReceipt``: submission acknowledgement, separate from completion, per
  ADR 0001 Decision 9.

Callers build terms; backends render them. Raw filter strings do not cross the
interface. This is ADR 0001 Decision 5 made concrete, and it keeps engine syntax
and authorization-relevant predicates out of application code.

``QueryShape`` is the declared counterpart: which fields may be filtered,
faceted or sorted, defaults, and the maximum page size. It is declared per use
case alongside the schema, not derived implicitly from capabilities.

``SearchResult.total_is_exact`` exists because engines differ: Meilisearch
returns an estimate, Typesense returns a count. A caller that pages to
completeness must know which one it received.

8. Reconcile, do not migrate
============================

Schema and settings changes are versioned and reconciled on every deploy, as
ADR 0001 Decision 6 requires. They are not expressed as Django migration files,
because migrations run once and the check has to run on every deploy.

Each backend owns its reconciliation strategy:

* Meilisearch applies settings with a ``PATCH``; changes to searchable,
  filterable or sortable attributes trigger a reindex.
* Typesense fixes settings at collection creation, so a change means creating a
  new collection and repointing an alias.
* A synchronous engine returns a completed receipt immediately; one with a task
  queue returns a receipt that a worker polls.

The library exposes one ``reconcile(schema)`` operation and one set of management
commands. Engine-specific mechanics stay in the backend.

9. Lossy edges are explicit
===========================

Anything a backend cannot represent must be reported by ``validate`` or
``configure``, never dropped silently. Options with no portable meaning live in
``extensions``, keyed by engine.

Known edges, recorded so they are not rediscovered:

* Meilisearch objects such as ``tags`` and ``collections`` are filterable as a
  whole; Typesense and Algolia need the leaf paths.
* Meilisearch searches every key of a free-form object; Typesense indexes only
  the keys the schema declares.
* Typesense ``max_facet_values`` defaults to 10 and caps the reported total, so
  faceted requests must set it explicitly. Meilisearch defaults to 100.
* Maximum hits per request differ (Meilisearch 1000, Typesense 250), so page
  size comes from the backend.
* Algolia has no per-field sort; sorting is expressed as replicas.
* Typesense has no collection-level stop-word list.

Consequences
************

1. One schema is authored, versioned, validated and tested. Adding a use case
   means writing a declaration, not another engine integration.
2. Backends stay small: capabilities, a renderer, document mapping and
   transport. They do not each define what a document is.
3. A use case that needs an unsupported capability fails at registration or
   startup, before data is indexed and before users see partial results.
4. Adding Algolia remains additive: capability flags plus a renderer. No schema
   or registration redesign is implied.
5. ``IndexSchema`` needs a version, and reconciliations must tolerate a backend
   being behind the declared version.
6. Every lossy edge needs a test. Engine backends must be verified against real
   engines, per ADR 0001 Decision 10; golden render files complement that but do
   not replace it.
7. ``content/search`` adopts first, with two registrations, one per Studio index.
   Its document builders and Celery tasks stay in ``openedx-platform``; only the
   engine layer moves.

Alternatives Considered
***********************

Each alternative is recorded with its strengths and costs. The Decision above
states the current preference; this section is input for upstream discussion,
not a claim that the alternatives are settled.

One authored schema plus a capability contract
==============================================

The approach in this ADR: one ``IndexSchema`` rendered by each backend, with
capability declarations and shared document validation.

Pros
----

* One vocabulary for use-case authors, backend authors and tests.
* A new capability is declared once; each renderer handles its encoding.
* Unsupported features fail at registration instead of being silently dropped.
* Adding Algolia is a capability set plus a renderer.

Cons
----

* The authored model is large: typing, nesting, seven capability flags and the
  settings blocks.
* Backends must understand the whole model, or rely on ``validate`` to reject
  the parts they cannot honour.
* It asks an initial adapter to support more than its first slice needs.

Narrow backend contract first, generalize later
===============================================

The shape of the initial adapter contribution
(``openedx/openedx-search#3``): a flat, string-only ``IndexDefinition`` with
searchable and filterable fields, exact ``FilterTerm`` values, bounded
pagination and write receipts, plus the benchmark harness in
``openedx/openedx-search#4``.

Pros
----

* Small review surface: contracts, two adapters and focused tests.
* Portability enforced at the contract (flat strings, exact filters, portable
  ids, 250 maximum page size).
* Ships a working, real-engine-verified slice early.
* The benchmark exercises pagination, filter leaks, partial imports and
  retrieval ceilings against both engines.
* A narrow, stable API is easier for a third-party backend to target.

Cons
----

* The contract cannot express the Studio documents: integer, float and datetime
  fields, nested paths, sortable, ranking and distinct.
* Either the contract grows into the full schema, or use cases are capped.
* Every capability added later needs a projection rule from the registration
  layer, with a risk of silent loss.
* Two vocabularies for contributors, and two places to change per capability.
* The benchmark fixtures are synthetic and flat, so they do not exercise the
  Studio document shape.

Separate document schema and settings models
============================================

Pros
----

* Mirrors ADR 0001's wording (document schema, index settings, query shape).
* A settings-only change does not touch the document schema.

Cons
----

* Field capabilities drive settings in every engine (``facetable`` becomes
  ``facet: true``, ``sortable`` becomes a per-field sort or a replica), so the
  two must stay in sync.
* More types, more validation, and a third object to version.

Raw filter strings
==================

Pros
----

* No translation layer; full engine expressiveness.
* Familiar to code that already builds engine filters, such as
  ``content/search`` today.

Cons
----

* Leaks engine syntax across boundaries.
* Authorization-relevant predicates are easy to get wrong.
* A second engine cannot reuse the same call sites.

Current preference
==================

One authored schema plus a capability-declaring backend protocol. It keeps a
single vocabulary, and lets a narrow initial slice exist as an internal
projection or a temporary adapter input without becoming the authored model.

References
**********

.. _0001-purpose-of-this-repo.rst: ./0001-purpose-of-this-repo.rst

* ADR 0001, "Purpose of This Repo" - ``docs/decisions/0001-purpose-of-this-repo.rst``
* ``content/search`` ADR 0001, "Studio Content Search Powered by Meilisearch" -
  https://github.com/openedx/openedx-platform/blob/master/openedx/core/djangoapps/content/search/docs/decisions/0001-meilisearch.rst
* ``content/search`` ADR 0002, "Separate Meilisearch Indexes for Course and
  Library Content" -
  https://github.com/openedx/openedx-platform/blob/master/openedx/core/djangoapps/content/search/docs/decisions/0002-separate-course-and-library-indexes.rst
* ``openedx/openedx-platform#38993``, indexing performance and asynchronous
  updates - https://github.com/openedx/openedx-platform/issues/38993
* ``openedx/modular-learning#245``, "Prototype Typesense search support" -
  https://github.com/openedx/modular-learning/issues/245
* ``openedx/openedx-search#3``, Meilisearch and Typesense document adapters -
  https://github.com/openedx/openedx-search/pull/3
* ``openedx/openedx-search#4``, library-search correctness benchmark -
  https://github.com/openedx/openedx-search/pull/4
* Typesense collection schema and nested fields -
  https://typesense.org/docs/30.2/api/collections.html
* Meilisearch settings -
  https://www.meilisearch.com/docs/reference/api/settings
* Algolia index settings -
  https://www.algolia.com/doc/api-reference/settings-api-parameters/
