Installation
============

``aerocoeff`` requires Python 3.12 or later. NumPy is its only runtime
dependency and is installed with it.

The package is not on PyPI. Install it from a wheel file, named like
``aerocoeff-0.1.0-py3-none-any.whl``, or from a copy of the source directory:

.. code-block:: console

   $ pip install aerocoeff-0.1.0-py3-none-any.whl
   $ pip install path/to/aerocoeff

In a project managed with `uv <https://docs.astral.sh/uv/>`__, use
``uv add`` with the same file or directory instead of ``pip install``.

Check the installation:

.. code-block:: console

   $ python -c "import aerocoeff; print(aerocoeff.__name__)"
   aerocoeff
