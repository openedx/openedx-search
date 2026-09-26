Getting Started
###############

This repository uses `uv`_ to manage its virtualenv and dependencies. Install
it first, then from the repository root run:

.. code-block:: bash

    $ make requirements

This creates ``.venv/`` from the committed ``uv.lock`` with every development
dependency group installed. Prefix commands with ``uv run`` (for example
``uv run pytest``) to run them in that environment; the ``make`` targets do
this for you.

.. _uv: https://docs.astral.sh/uv/

Changing dependencies
*********************

Dependencies are declared in ``pyproject.toml``: runtime dependencies under
``[project].dependencies`` and development tools under
``[dependency-groups]``. After editing them, run ``make compile-requirements``
to update ``uv.lock`` without upgrading anything else, and commit both files.

``make upgrade`` re-resolves everything to the newest allowed versions and
regenerates ``[tool.uv].constraint-dependencies`` from edx-lint. Do not edit
that list by hand; put repo-specific constraints in
``[tool.edx_lint].uv_constraints`` instead.

See `How To Manage a uv Dependency Version Matrix`_ for adding or retiring a
Django version from the test matrix.

.. _How To Manage a uv Dependency Version Matrix: https://docs.openedx.org/en/latest/developers/how-tos/manage-uv-dependency-matrix.html

Releases
********

Releases are automated with `python-semantic-release`_. Merging to ``main``
publishes a new version to PyPI when the merged commits warrant one, so commit
messages must follow the `Conventional Commits`_ format described in
`OEP-51`_: ``feat:`` makes a minor release, ``fix:``, ``perf:`` and
``build:`` make a patch release, and a ``!`` or ``BREAKING CHANGE:`` footer
makes a major release.

.. _python-semantic-release: https://python-semantic-release.readthedocs.io/
.. _Conventional Commits: https://www.conventionalcommits.org/
.. _OEP-51: https://docs.openedx.org/projects/openedx-proposals/en/latest/best-practices/oep-0051-bp-conventional-commits.html
