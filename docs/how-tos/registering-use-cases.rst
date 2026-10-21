Registering a use case
######################

The registration API is engine-neutral. A use case declares its logical index,
schema and document types; the deployment chooses the backend.

.. code-block:: python

    from openedx_search import get_registration, register_use_case
    from openedx_search.samples import STUDIO_COURSE

    register_use_case(STUDIO_COURSE)
    registration = get_registration("studio_course")
    print(registration.index)  # studio_content

``openedx_search.samples`` holds the full ``IndexSchema``: typed fields, nested
paths, capability flags, ranking rules and a distinct attribute. ``schema.py``
holds the model and ``registry.py`` the registration API.

Backend selection
*****************

Deployments choose the engine in configuration, not in the registration:

.. code-block:: python

    OPENEDX_SEARCH_BACKENDS = {
        "default": {"engine": "meilisearch", "url": "http://...", "api_key": "..."},
    }
    OPENEDX_SEARCH_DEFAULT_BACKEND = "default"
    OPENEDX_SEARCH_USE_CASE_BACKENDS = {"forum": "typesense"}  # optional

``get_backend_config(use_case)`` resolves the override first, then the default,
and raises ``BackendNotConfigured`` when neither is set. The library ships no
default engine on purpose.

Loading registrations
*********************

Registrations are consumer-owned. Call ``register_use_case`` from the consumer's
``AppConfig.ready()``:

.. code-block:: python

    from django.apps import AppConfig

    from openedx_search import register_use_case
    from openedx_search.samples import STUDIO_COURSE, STUDIO_LIBRARY


    class StudioSearchConfig(AppConfig):
        name = "studio_search"

        def ready(self):
            register_use_case(STUDIO_COURSE, replace=True)
            register_use_case(STUDIO_LIBRARY, replace=True)

``replace=True`` makes the hook safe under development reloads and repeated
``ready()`` calls in tests. Each process loads its own in-memory registry; there
is no shared or persisted state.

