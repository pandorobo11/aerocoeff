"""Reference quantities and six-component aerodynamic coefficients (ADR 0001)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from aerocoeff._validation import FloatArray, finite_array, positive_scalar, vector3_array
from aerocoeff.frames import Frame


@dataclass(frozen=True)
class ReferenceQuantities:
    """Reference area and per-axis moment reference lengths, in SI units.

    ``Cl = L / (q S l_roll)``, ``Cm = M / (q S l_pitch)``, ``Cn = N / (q S l_yaw)``.
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
