"""Control-surface hinge frame and three-component loads (ADR 0003)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike

from aerocoeff._validation import FloatArray, positive_scalar, vector3_array
from aerocoeff.coefficients import AeroCoefficients, ReferenceQuantities
from aerocoeff.frames import Frame, _angle_rad

TRAILING_EDGE_RTOL = 1e-6
"""Smallest accepted ratio of the trailing-edge direction's part perpendicular to
the hinge axis to its full length."""


def _single_vector(value: ArrayLike, name: str) -> FloatArray:
    vector = vector3_array(value, name)
    if vector.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {vector.shape}")
    return vector


def _deflection_rotation(deflection_rad: FloatArray) -> FloatArray:
    # Right-hand rotation about y_h: x_h = c x0 - s z0, z_h = s x0 + c z0 (ADR 0003).
    c, s = np.cos(deflection_rad), np.sin(deflection_rad)
    zero, one = np.zeros_like(c), np.ones_like(c)
    rows = (
        np.stack([c, zero, -s], -1),
        np.stack([zero, one, zero], -1),
        np.stack([s, zero, c], -1),
    )
    return np.stack(rows, axis=-2)


@dataclass(frozen=True, eq=False, kw_only=True)
class ControlSurface:
    """A control surface described by its hinge line, in meters in ``points_frame``.

    The hinge axis ``y_h`` points from ``hinge_start_m`` to ``hinge_end_m``;
    ``x_h`` is the part of ``trailing_edge_direction`` (undeflected surface)
    perpendicular to it, and ``z_h = x_h x y_h``. Loads are taken about
    ``hinge_start_m`` and normalized with ``area_m2`` and the component-named
    lengths: ``Ch`` with ``hinge_moment_length_m``, ``CB`` with
    ``bending_moment_length_m``, and ``Cn_h`` with ``normal_moment_length_m``,
    which defaults to ``bending_moment_length_m`` (ADR 0003).
    """

    #: Start of the hinge line and moment reference point of the surface loads, shape ``(3,)``.
    hinge_start_m: FloatArray
    #: End of the hinge line; the hinge axis points from start to end, shape ``(3,)``.
    hinge_end_m: FloatArray
    #: From the hinge toward the trailing edge of the undeflected surface; length irrelevant.
    trailing_edge_direction: FloatArray
    #: Frame of the points and the direction; a single frame without batch.
    points_frame: Frame
    #: Surface reference area ``S_s``, in m^2.
    area_m2: float
    #: Length that normalizes the hinge moment ``Ch``, in m.
    hinge_moment_length_m: float
    #: Length that normalizes the root bending moment ``CB``, in m.
    bending_moment_length_m: float
    #: Length that normalizes ``Cn_h``, in m; defaults to ``bending_moment_length_m``.
    normal_moment_length_m: float | None = None
    _undeflected_from_body: FloatArray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.points_frame, Frame):
            raise TypeError("points_frame must be a Frame")
        if self.points_frame.batch_shape != ():
            raise ValueError(
                f"points_frame must be a single frame, got batch shape "
                f"{self.points_frame.batch_shape}"
            )
        start = _single_vector(self.hinge_start_m, "hinge_start_m")
        end = _single_vector(self.hinge_end_m, "hinge_end_m")
        direction = _single_vector(self.trailing_edge_direction, "trailing_edge_direction")
        for name in ("area_m2", "hinge_moment_length_m", "bending_moment_length_m"):
            object.__setattr__(self, name, positive_scalar(getattr(self, name), name))
        normal_length = (
            self.bending_moment_length_m
            if self.normal_moment_length_m is None
            else positive_scalar(self.normal_moment_length_m, "normal_moment_length_m")
        )

        body_from_points = self.points_frame.rotation_from_body.T
        hinge = body_from_points @ (end - start)
        hinge_length = np.linalg.norm(hinge)
        if hinge_length == 0.0:
            raise ValueError("hinge_start_m and hinge_end_m must be different points")
        y_axis = hinge / hinge_length
        trailing = body_from_points @ direction
        perpendicular = trailing - (trailing @ y_axis) * y_axis
        perpendicular_length = np.linalg.norm(perpendicular)
        if perpendicular_length <= TRAILING_EDGE_RTOL * np.linalg.norm(trailing):
            raise ValueError(
                "trailing_edge_direction must not be zero or parallel to the hinge axis"
            )
        x_axis = perpendicular / perpendicular_length
        undeflected = np.stack([x_axis, y_axis, np.cross(x_axis, y_axis)])
        undeflected.flags.writeable = False

        object.__setattr__(self, "hinge_start_m", start)
        object.__setattr__(self, "hinge_end_m", end)
        object.__setattr__(self, "trailing_edge_direction", direction)
        object.__setattr__(self, "normal_moment_length_m", normal_length)
        object.__setattr__(self, "_undeflected_from_body", undeflected)

    @property
    def reference(self) -> ReferenceQuantities:
        """Surface reference in hinge-frame axis positions: x bending, y hinge, z normal."""
        assert self.normal_moment_length_m is not None
        return ReferenceQuantities(
            area_m2=self.area_m2,
            length_roll_m=self.bending_moment_length_m,
            length_pitch_m=self.hinge_moment_length_m,
            length_yaw_m=self.normal_moment_length_m,
        )

    def frame(
        self, *, deflection_rad: ArrayLike | None = None, deflection_deg: ArrayLike | None = None
    ) -> Frame:
        """Return the hinge frame for a deflection; give exactly one of the two.

        A positive deflection is a right-hand rotation about the hinge axis, which
        moves the trailing edge toward ``-z`` of the undeflected surface.
        """
        deflection = _angle_rad(deflection_rad, deflection_deg, "deflection")
        rotation = _deflection_rotation(deflection) @ self._undeflected_from_body
        return Frame.from_matrix(rotation, name="hinge")

    def loads(
        self,
        coefficients: AeroCoefficients,
        *,
        moment_reference_m: ArrayLike,
        deflection_rad: ArrayLike | None = None,
        deflection_deg: ArrayLike | None = None,
    ) -> AeroCoefficients:
        """Express the surface load in the hinge frame, about ``hinge_start_m``.

        ``coefficients`` is the load on this surface alone, taken about
        ``moment_reference_m`` (in ``points_frame``) and normalized with any
        reference; it may be in any frame.
        """
        if not isinstance(coefficients, AeroCoefficients):
            raise TypeError("coefficients must be AeroCoefficients")
        return coefficients.transform(
            frame=self.frame(deflection_rad=deflection_rad, deflection_deg=deflection_deg),
            reference=self.reference,
            from_point_m=moment_reference_m,
            to_point_m=self.hinge_start_m,
            points_frame=self.points_frame,
        )

    def three_components_array(
        self,
        coefficients: AeroCoefficients,
        *,
        moment_reference_m: ArrayLike,
        deflection_rad: ArrayLike | None = None,
        deflection_deg: ArrayLike | None = None,
    ) -> FloatArray:
        """Return a new ``(..., 3)`` array ordered ``CN_s, Ch, CB`` (ADR 0003):
        normal force along ``z_h``, hinge moment about ``y_h``, and root bending
        moment about ``x_h``.
        """
        loads = self.loads(
            coefficients,
            moment_reference_m=moment_reference_m,
            deflection_rad=deflection_rad,
            deflection_deg=deflection_deg,
        )
        return np.stack([loads.CZ, loads.Cm, loads.Cl], axis=-1)
