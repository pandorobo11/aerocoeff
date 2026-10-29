aerocoeff
=========

``aerocoeff`` transforms six-component aerodynamic coefficients between
reference frames, moment reference points, and reference quantities,
re-expresses a control-surface load as its own three components, and converts
coefficients to and from forces and moments.

Frames, signs, and angle units are always explicit. The default frame is the
body frame (x forward, y toward the right wing, z down), all quantities are in
SI units, and NumPy is the only runtime dependency.

Start with the :doc:`getting_started/quickstart`, and read
:doc:`getting_started/conventions` before relying on a sign or a frame. The
:doc:`guides/index` work through every operation with checked examples, and the
:doc:`api/index` lists the public classes and methods.

The conventions are fixed by the accepted
`architecture decision records <https://github.com/pandorobo11/aerocoeff/blob/main/devdocs/adr/README.md>`__.
If this manual and an ADR ever disagree, the ADR applies.

.. toctree::
   :maxdepth: 2
   :titlesonly:

   getting_started/index
   guides/index
   api/index
