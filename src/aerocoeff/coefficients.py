"""Reference quantities and six-component aerodynamic coefficients (ADR 0001, ADR 0002)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from aerocoeff._validation import FloatArray, finite_array, positive_scalar, vector3_array
from aerocoeff.frames import Frame, FrameKind

# Largest |CY|, |Cl|, |Cn| accepted as zero by the longitudinal outputs; covers the
# rounding left by rotations that return to the longitudinal plane.
LATERAL_ATOL = 1e-12


def _columns(array: ArrayLike, count: int) -> FloatArray:
    values = finite_array(array, "array")
    if values.ndim < 1 or values.shape[-1] != count:
        raise ValueError(f"array must have shape (..., {count}), got {values.shape}")
    return values


@dataclass(frozen=True)
class ReferenceQuantities:
    """Reference area and per-axis moment reference lengths, in SI units.

    ``Cl = L / (q S l_roll)``, ``Cm = M / (q S l_pitch)``, ``Cn = N / (q S l_yaw)``.

    The lengths belong to the axis positions of whatever frame the coefficients
    are in: the x-, y-, and z-axis moments are divided by ``l_roll``, ``l_pitch``,
    and ``l_yaw`` respectively, in every frame (ADR 0001). The area has no
    direction.
    """

    area_m2: float
    length_roll_m: float
    length_pitch_m: float
    length_yaw_m: float

    def __post_init__(self) -> None:
        for field in ("area_m2", "length_roll_m", "length_pitch_m", "length_yaw_m"):
            object.__setattr__(self, field, positive_scalar(getattr(self, field), field))

    @classmethod
    def from_span_chord(cls, area_m2: float, span_m: float, chord_m: float) -> ReferenceQuantities:
        """Use the span for roll and yaw and the chord for pitch."""
        return cls(area_m2, span_m, chord_m, span_m)

    @property
    def moment_lengths_m(self) -> FloatArray:
        """``(l_roll, l_pitch, l_yaw)`` as an array."""
        lengths = np.array([self.length_roll_m, self.length_pitch_m, self.length_yaw_m])
        lengths.flags.writeable = False
        return lengths


@dataclass(frozen=True, eq=False)
class AeroCoefficients:
    """Six-component coefficients in a named frame.

    ``force`` holds ``(CX, CY, CZ)`` and ``moment`` holds ``(Cl, Cm, Cn)`` along and
    about the axes of ``frame``, each with shape ``(..., 3)``. Moments are taken
    about the moment reference point and normalized with ``reference``.
    """

    force: FloatArray
    moment: FloatArray
    frame: Frame
    reference: ReferenceQuantities

    def __post_init__(self) -> None:
        force = vector3_array(self.force, "force")
        moment = vector3_array(self.moment, "moment")
        if force.shape != moment.shape:
            raise ValueError(
                f"force and moment must have the same shape, got {force.shape} and {moment.shape}"
            )
        if not isinstance(self.frame, Frame):
            raise TypeError("frame must be a Frame")
        if not isinstance(self.reference, ReferenceQuantities):
            raise TypeError("reference must be ReferenceQuantities")
        try:
            np.broadcast_shapes(self.frame.batch_shape, force.shape[:-1])
        except ValueError as error:
            raise ValueError(
                f"frame batch shape {self.frame.batch_shape} does not broadcast with "
                f"coefficient batch shape {force.shape[:-1]}"
            ) from error
        object.__setattr__(self, "force", force)
        object.__setattr__(self, "moment", moment)

    @classmethod
    def from_components(
        cls,
        *,
        CX: ArrayLike,
        CY: ArrayLike,
        CZ: ArrayLike,
        Cl: ArrayLike,
        Cm: ArrayLike,
        Cn: ArrayLike,
        reference: ReferenceQuantities,
        frame: Frame | None = None,
    ) -> AeroCoefficients:
        """Build from six broadcastable components; ``frame`` defaults to the body frame."""
        named = {"CX": CX, "CY": CY, "CZ": CZ, "Cl": Cl, "Cm": Cm, "Cn": Cn}
        components = np.broadcast_arrays(
            *(finite_array(value, name) for name, value in named.items())
        )
        return cls(
            force=np.stack(components[:3], axis=-1),
            moment=np.stack(components[3:], axis=-1),
            frame=Frame.body() if frame is None else frame,
            reference=reference,
        )

    @classmethod
    def from_components_array(
        cls,
        array: ArrayLike,
        *,
        reference: ReferenceQuantities,
        frame: Frame | None = None,
    ) -> AeroCoefficients:
        """Build from an array of shape ``(..., 6)`` ordered ``CX, CY, CZ, Cl, Cm, Cn``.

        The components are in ``frame``, which defaults to the body frame. Columns
        are always frame components: in stability axes they are ``-CD, CY, -CL``,
        not ``CD, CY, CL`` (use :meth:`from_lift_drag_array` for those). This is
        the inverse of :meth:`to_components_array`.
        """
        values = _columns(array, 6)
        return cls(
            force=values[..., :3],
            moment=values[..., 3:],
            frame=Frame.body() if frame is None else frame,
            reference=reference,
        )

    @classmethod
    def from_axial_normal(
        cls,
        *,
        CA: ArrayLike,
        CY: ArrayLike,
        CN: ArrayLike,
        Cl: ArrayLike,
        Cm: ArrayLike,
        Cn: ArrayLike,
        reference: ReferenceQuantities,
    ) -> AeroCoefficients:
        """Build body-frame coefficients from axial and normal force (``CX = -CA``, ``CZ = -CN``).

        This matches the body-axis output of panelsolver.
        """
        CA_array = finite_array(CA, "CA")
        CN_array = finite_array(CN, "CN")
        return cls.from_components(
            CX=-CA_array, CY=CY, CZ=-CN_array, Cl=Cl, Cm=Cm, Cn=Cn, reference=reference
        )

    @classmethod
    def from_axial_normal_array(
        cls, array: ArrayLike, *, reference: ReferenceQuantities
    ) -> AeroCoefficients:
        """Build body-frame coefficients from a ``(..., 6)`` array ordered
        ``CA, CY, CN, Cl, Cm, Cn``. This is the inverse of :meth:`to_axial_normal_array`.
        """
        values = _columns(array, 6)
        return cls.from_axial_normal(
            CA=values[..., 0],
            CY=values[..., 1],
            CN=values[..., 2],
            Cl=values[..., 3],
            Cm=values[..., 4],
            Cn=values[..., 5],
            reference=reference,
        )

    @classmethod
    def from_lift_drag(
        cls,
        *,
        CD: ArrayLike,
        CY: ArrayLike,
        CL: ArrayLike,
        Cl: ArrayLike,
        Cm: ArrayLike,
        Cn: ArrayLike,
        reference: ReferenceQuantities,
        alpha_rad: ArrayLike | None = None,
        alpha_deg: ArrayLike | None = None,
    ) -> AeroCoefficients:
        """Build stability-frame coefficients from drag, side force, and lift.

        ``CX = -CD`` and ``CZ = -CL`` (ADR 0001). All six components, including the
        moments, are in stability axes. Give exactly one of ``alpha_rad`` and
        ``alpha_deg``.
        """
        frame = Frame.stability(alpha_rad=alpha_rad, alpha_deg=alpha_deg)
        CD_array = finite_array(CD, "CD")
        CL_array = finite_array(CL, "CL")
        return cls.from_components(
            CX=-CD_array, CY=CY, CZ=-CL_array, Cl=Cl, Cm=Cm, Cn=Cn, reference=reference, frame=frame
        )

    @classmethod
    def from_lift_drag_array(
        cls,
        array: ArrayLike,
        *,
        reference: ReferenceQuantities,
        alpha_rad: ArrayLike | None = None,
        alpha_deg: ArrayLike | None = None,
    ) -> AeroCoefficients:
        """Build stability-frame coefficients from a ``(..., 6)`` array ordered
        ``CD, CY, CL, Cl, Cm, Cn``, all in stability axes. This is the inverse of
        :meth:`to_lift_drag_array`.
        """
        values = _columns(array, 6)
        return cls.from_lift_drag(
            CD=values[..., 0],
            CY=values[..., 1],
            CL=values[..., 2],
            Cl=values[..., 3],
            Cm=values[..., 4],
            Cn=values[..., 5],
            reference=reference,
            alpha_rad=alpha_rad,
            alpha_deg=alpha_deg,
        )

    @classmethod
    def from_longitudinal_axial_normal(
        cls, *, CA: ArrayLike, CN: ArrayLike, Cm: ArrayLike, reference: ReferenceQuantities
    ) -> AeroCoefficients:
        """Build body-frame coefficients from ``CA``, ``CN``, and ``Cm``, with
        ``CY = Cl = Cn = 0``.
        """
        return cls.from_axial_normal(
            CA=CA, CY=0.0, CN=CN, Cl=0.0, Cm=Cm, Cn=0.0, reference=reference
        )

    @classmethod
    def from_longitudinal_axial_normal_array(
        cls, array: ArrayLike, *, reference: ReferenceQuantities
    ) -> AeroCoefficients:
        """Build body-frame coefficients from a ``(..., 3)`` array ordered ``CA, CN, Cm``.

        This is the inverse of :meth:`to_longitudinal_axial_normal_array`.
        """
        values = _columns(array, 3)
        return cls.from_longitudinal_axial_normal(
            CA=values[..., 0], CN=values[..., 1], Cm=values[..., 2], reference=reference
        )

    @classmethod
    def from_longitudinal_lift_drag(
        cls,
        *,
        CD: ArrayLike,
        CL: ArrayLike,
        Cm: ArrayLike,
        reference: ReferenceQuantities,
        alpha_rad: ArrayLike | None = None,
        alpha_deg: ArrayLike | None = None,
    ) -> AeroCoefficients:
        """Build stability-frame coefficients from ``CD``, ``CL``, and ``Cm``, with
        ``CY = Cl = Cn = 0``. Give exactly one of ``alpha_rad`` and ``alpha_deg``.
        """
        return cls.from_lift_drag(
            CD=CD,
            CY=0.0,
            CL=CL,
            Cl=0.0,
            Cm=Cm,
            Cn=0.0,
            reference=reference,
            alpha_rad=alpha_rad,
            alpha_deg=alpha_deg,
        )

    @classmethod
    def from_longitudinal_lift_drag_array(
        cls,
        array: ArrayLike,
        *,
        reference: ReferenceQuantities,
        alpha_rad: ArrayLike | None = None,
        alpha_deg: ArrayLike | None = None,
    ) -> AeroCoefficients:
        """Build stability-frame coefficients from a ``(..., 3)`` array ordered
        ``CD, CL, Cm``. This is the inverse of :meth:`to_longitudinal_lift_drag_array`.
        """
        values = _columns(array, 3)
        return cls.from_longitudinal_lift_drag(
            CD=values[..., 0],
            CL=values[..., 1],
            Cm=values[..., 2],
            reference=reference,
            alpha_rad=alpha_rad,
            alpha_deg=alpha_deg,
        )

    def to_frame(self, frame: Frame) -> AeroCoefficients:
        """Express the coefficients in ``frame`` about the same moment reference point.

        Forces are rotated directly. Moments are rotated as the length-scaled vector
        ``(Cl l_roll, Cm l_pitch, Cn l_yaw)`` and renormalized (ADR 0001).

        The reference quantities are kept, so in the result the x-, y-, and z-axis
        moments of ``frame`` are again divided by ``l_roll``, ``l_pitch``, and
        ``l_yaw``. For a frame that permutes the axes, such as ``"RDF"``, these
        lengths no longer match roll, pitch, and yaw.
        """
        if not isinstance(frame, Frame):
            raise TypeError("frame must be a Frame")
        relative = frame.rotation_from_body @ np.swapaxes(self.frame.rotation_from_body, -1, -2)
        lengths = self.reference.moment_lengths_m
        force = (relative @ self.force[..., np.newaxis])[..., 0]
        moment = (relative @ (self.moment * lengths)[..., np.newaxis])[..., 0] / lengths
        return AeroCoefficients(force, moment, frame, self.reference)

    def with_reference(self, reference: ReferenceQuantities) -> AeroCoefficients:
        """Renormalize to ``reference`` in the same frame and about the same point.

        ``C_F' = C_F S / S'`` and ``C_M' = C_M (S l) / (S' l')`` per axis position
        (ADR 0002).
        """
        if not isinstance(reference, ReferenceQuantities):
            raise TypeError("reference must be ReferenceQuantities")
        area_ratio = self.reference.area_m2 / reference.area_m2
        length_ratio = self.reference.moment_lengths_m / reference.moment_lengths_m
        return AeroCoefficients(
            self.force * area_ratio,
            self.moment * (area_ratio * length_ratio),
            self.frame,
            reference,
        )

    def transfer_moment_reference(
        self, *, from_point_m: ArrayLike, to_point_m: ArrayLike, points_frame: Frame
    ) -> AeroCoefficients:
        """Move the moment reference point from ``from_point_m`` to ``to_point_m``.

        ``C_M,to = (l C_M,from + d x C_F) / l`` with ``d = r_from - r_to`` rotated
        into this frame (ADR 0002). Both points are in ``points_frame``, in meters,
        with a shared arbitrary origin; ``points_frame`` has no default because
        points are often given in ``BRU``. Forces and reference quantities are
        unchanged.
        """
        if not isinstance(points_frame, Frame):
            raise TypeError("points_frame must be a Frame")
        from_point = vector3_array(from_point_m, "from_point_m")
        to_point = vector3_array(to_point_m, "to_point_m")
        try:
            np.broadcast_shapes(
                self.force.shape[:-1],
                self.frame.batch_shape,
                from_point.shape[:-1],
                to_point.shape[:-1],
                points_frame.batch_shape,
            )
        except ValueError as error:
            raise ValueError(
                f"point batch shapes {from_point.shape[:-1]} and {to_point.shape[:-1]} and "
                f"points_frame batch shape {points_frame.batch_shape} do not broadcast with "
                f"coefficient batch shape {self.force.shape[:-1]}"
            ) from error
        relative = self.frame.rotation_from_body @ np.swapaxes(
            points_frame.rotation_from_body, -1, -2
        )
        displacement = (relative @ (from_point - to_point)[..., np.newaxis])[..., 0]
        lengths = self.reference.moment_lengths_m
        moment = (self.moment * lengths + np.cross(displacement, self.force)) / lengths
        force = np.broadcast_to(self.force, moment.shape)
        return AeroCoefficients(force, moment, self.frame, self.reference)

    def transform(
        self,
        *,
        frame: Frame | None = None,
        reference: ReferenceQuantities | None = None,
        from_point_m: ArrayLike | None = None,
        to_point_m: ArrayLike | None = None,
        points_frame: Frame | None = None,
    ) -> AeroCoefficients:
        """Apply any combination of a moment reference transfer, a frame change, and a
        reference-quantity change (ADR 0002).

        The operations are exact in forces and moments per unit dynamic pressure,
        so their order does not matter. Give ``from_point_m``, ``to_point_m``, and
        ``points_frame`` together or not at all; ``reference`` lengths belong to
        the axis positions of ``frame``.
        """
        result = self
        if from_point_m is not None and to_point_m is not None and points_frame is not None:
            result = result.transfer_moment_reference(
                from_point_m=from_point_m, to_point_m=to_point_m, points_frame=points_frame
            )
        elif from_point_m is not None or to_point_m is not None or points_frame is not None:
            raise TypeError(
                "give from_point_m, to_point_m, and points_frame together or not at all"
            )
        if frame is not None:
            result = result.to_frame(frame)
        if reference is not None:
            result = result.with_reference(reference)
        return result

    def to_body(self) -> AeroCoefficients:
        """Express the coefficients in the body frame, FRD."""
        return self.to_frame(Frame.body())

    def to_components_array(self) -> FloatArray:
        """Return a new ``(..., 6)`` array ordered ``CX, CY, CZ, Cl, Cm, Cn`` in this frame."""
        return np.concatenate([self.force, self.moment], axis=-1)

    def to_axial_normal_array(self) -> FloatArray:
        """Return a new ``(..., 6)`` array ordered ``CA, CY, CN, Cl, Cm, Cn``.

        Only defined in the body frame.
        """
        self._require_kind("body", "the axial-normal array")
        return np.stack([self.CA, self.CY, self.CN, self.Cl, self.Cm, self.Cn], axis=-1)

    def to_lift_drag_array(self) -> FloatArray:
        """Return a new ``(..., 6)`` array ordered ``CD, CY, CL, Cl, Cm, Cn``.

        Only defined in the stability frame.
        """
        self._require_kind("stability", "the lift-drag array")
        return np.stack([self.CD, self.CY, self.CL, self.Cl, self.Cm, self.Cn], axis=-1)

    def to_longitudinal_axial_normal_array(self) -> FloatArray:
        """Return a new ``(..., 3)`` array ordered ``CA, CN, Cm``.

        Only defined in the body frame, and only when ``CY``, ``Cl``, and ``Cn`` are
        zero within :data:`LATERAL_ATOL`; lateral components are never dropped.
        """
        self._require_kind("body", "the longitudinal axial-normal array")
        self._require_longitudinal()
        return np.stack([self.CA, self.CN, self.Cm], axis=-1)

    def to_longitudinal_lift_drag_array(self) -> FloatArray:
        """Return a new ``(..., 3)`` array ordered ``CD, CL, Cm``.

        Only defined in the stability frame, and only when ``CY``, ``Cl``, and ``Cn``
        are zero within :data:`LATERAL_ATOL`; lateral components are never dropped.
        """
        self._require_kind("stability", "the longitudinal lift-drag array")
        self._require_longitudinal()
        return np.stack([self.CD, self.CL, self.Cm], axis=-1)

    def _require_longitudinal(self) -> None:
        lateral = np.abs(np.stack([self.CY, self.Cl, self.Cn], axis=-1))
        largest = float(np.max(lateral, initial=0.0))
        if largest > LATERAL_ATOL:
            raise ValueError(
                f"longitudinal output needs CY, Cl, and Cn within {LATERAL_ATOL:g} of zero, "
                f"but the largest magnitude is {largest:.3g}; use the six-column array instead"
            )

    def _require_kind(self, kind: FrameKind, quantity: str) -> None:
        if self.frame.kind != kind:
            raise ValueError(
                f"{quantity} is defined in {kind} axes, but these coefficients are in the "
                f"{self.frame.name!r} frame; convert them with to_frame() first"
            )

    @property
    def CA(self) -> FloatArray:
        """Axial force, ``-CX_body``."""
        self._require_kind("body", "CA")
        return -self.force[..., 0]

    @property
    def CN(self) -> FloatArray:
        """Normal force, ``-CZ_body``."""
        self._require_kind("body", "CN")
        return -self.force[..., 2]

    @property
    def CD(self) -> FloatArray:
        """Drag, ``-CX_stability``."""
        self._require_kind("stability", "CD")
        return -self.force[..., 0]

    @property
    def CL(self) -> FloatArray:
        """Lift, ``-CZ_stability``."""
        self._require_kind("stability", "CL")
        return -self.force[..., 2]

    @property
    def CX(self) -> FloatArray:
        return self.force[..., 0]

    @property
    def CY(self) -> FloatArray:
        return self.force[..., 1]

    @property
    def CZ(self) -> FloatArray:
        return self.force[..., 2]

    @property
    def Cl(self) -> FloatArray:
        return self.moment[..., 0]

    @property
    def Cm(self) -> FloatArray:
        return self.moment[..., 1]

    @property
    def Cn(self) -> FloatArray:
        return self.moment[..., 2]
