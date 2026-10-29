"""Coordinate frames defined by their orientation relative to the body frame.

Conventions follow ADR 0001: the body frame is FRD (x forward, y toward the right
wing, z down), every frame is right-handed, and a frame is stored as the rotation
``R`` with ``v_frame = R @ v_body``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike

from aerocoeff._validation import FloatArray, finite_array

ROTATION_ATOL = 1e-9
"""Absolute tolerance for orthonormality and determinant checks of rotations."""

FrameKind = Literal["body", "stability", "wind", "custom"]

_DIRECTIONS_BODY: dict[str, tuple[float, float, float]] = {
    "F": (1.0, 0.0, 0.0),
    "B": (-1.0, 0.0, 0.0),
    "R": (0.0, 1.0, 0.0),
    "L": (0.0, -1.0, 0.0),
    "D": (0.0, 0.0, 1.0),
    "U": (0.0, 0.0, -1.0),
}
_OPPOSITE_PAIRS = ("FB", "RL", "DU")
_KINDS: tuple[FrameKind, ...] = ("body", "stability", "wind", "custom")


def _validated_rotation(matrix: ArrayLike, name: str) -> FloatArray:
    rotation = finite_array(matrix, name)
    if rotation.ndim < 2 or rotation.shape[-2:] != (3, 3):
        raise ValueError(f"{name} must have shape (..., 3, 3), got {rotation.shape}")
    gram = rotation @ np.swapaxes(rotation, -1, -2)
    if not np.allclose(gram, np.eye(3), rtol=0.0, atol=ROTATION_ATOL):
        raise ValueError(f"{name} must be orthonormal within {ROTATION_ATOL}")
    if not np.allclose(np.linalg.det(rotation), 1.0, rtol=0.0, atol=ROTATION_ATOL):
        raise ValueError(f"{name} must be right-handed (determinant +1 within {ROTATION_ATOL})")
    return rotation


def _kind_matches(rotation: FloatArray, kind: FrameKind) -> bool:
    if kind == "body":
        return bool(np.allclose(rotation, np.eye(3), rtol=0.0, atol=ROTATION_ATOL))
    if kind == "stability":
        # A rotation about y_body keeps y_stability = y_body.
        return bool(np.allclose(rotation[..., 1, :], [0.0, 1.0, 0.0], rtol=0.0, atol=ROTATION_ATOL))
    if kind == "wind":
        # z_wind = z_stability is perpendicular to y_body.
        return bool(np.allclose(rotation[..., 2, 1], 0.0, rtol=0.0, atol=ROTATION_ATOL))
    return True


def _angle_rad(rad: ArrayLike | None, deg: ArrayLike | None, name: str) -> FloatArray:
    if (rad is None) == (deg is None):
        raise TypeError(f"give exactly one of {name}_rad and {name}_deg")
    if rad is not None:
        return finite_array(rad, f"{name}_rad")
    assert deg is not None
    return np.deg2rad(finite_array(deg, f"{name}_deg"))


def _stability_from_body(alpha_rad: FloatArray) -> FloatArray:
    c, s = np.cos(alpha_rad), np.sin(alpha_rad)
    zero, one = np.zeros_like(c), np.ones_like(c)
    rows = (
        np.stack([c, zero, s], -1),
        np.stack([zero, one, zero], -1),
        np.stack([-s, zero, c], -1),
    )
    return np.stack(rows, axis=-2)


def _wind_from_stability(beta_rad: FloatArray) -> FloatArray:
    c, s = np.cos(beta_rad), np.sin(beta_rad)
    zero, one = np.zeros_like(c), np.ones_like(c)
    rows = (
        np.stack([c, s, zero], -1),
        np.stack([-s, c, zero], -1),
        np.stack([zero, zero, one], -1),
    )
    return np.stack(rows, axis=-2)


@dataclass(frozen=True, eq=False)
class Frame:
    """A right-handed frame given by ``rotation_from_body`` (``v_frame = R @ v_body``).

    ``rotation_from_body`` has shape ``(..., 3, 3)`` so that one frame object can
    describe a batch of orientations. ``kind`` marks the body, stability, and wind
    frames, in which the named coefficients (``CA``, ``CD``, ...) are defined;
    a kind other than ``"custom"`` is checked against the rotation.
    """

    #: Rotation ``R`` with ``v_frame = R @ v_body``, shape ``(..., 3, 3)``.
    rotation_from_body: FloatArray
    #: Name used in messages, such as ``"FRD"`` or ``"stability"``.
    name: str
    #: ``"body"``, ``"stability"``, ``"wind"``, or ``"custom"``; checked against the rotation.
    kind: FrameKind = "custom"

    def __post_init__(self) -> None:
        rotation = _validated_rotation(self.rotation_from_body, "rotation_from_body")
        object.__setattr__(self, "rotation_from_body", rotation)
        if not isinstance(self.name, str) or not self.name:
            raise TypeError("name must be a non-empty string")
        if self.kind not in _KINDS:
            raise ValueError(f"kind must be one of {_KINDS}, got {self.kind!r}")
        if not _kind_matches(rotation, self.kind):
            raise ValueError(f"rotation_from_body is not a {self.kind} frame orientation")

    @classmethod
    def body(cls) -> Frame:
        """The default body frame, FRD."""
        return cls.from_axes("FRD")

    @classmethod
    def from_axes(cls, axes: str) -> Frame:
        """Build a frame from three body-direction letters for its x, y, and z axes.

        Letters are F/B (forward/back), R/L (right/left wing), and D/U (down/up),
        one from each pair, in any order. For example, ``"FRD"`` is the body frame
        and ``"BRU"`` (x back, y right, z up) is common in CAD models.
        """
        if not isinstance(axes, str):
            raise TypeError("axes must be a string such as 'FRD'")
        letters = axes.upper()
        if len(letters) != 3 or any(letter not in _DIRECTIONS_BODY for letter in letters):
            raise ValueError(f"axes must be three of the letters F, B, R, L, D, U, got {axes!r}")
        for pair in _OPPOSITE_PAIRS:
            if sum(letter in pair for letter in letters) != 1:
                raise ValueError(f"axes must use exactly one of {pair[0]}/{pair[1]}, got {axes!r}")
        rotation = np.array([_DIRECTIONS_BODY[letter] for letter in letters])
        if np.linalg.det(rotation) < 0.0:
            raise ValueError(f"axes {axes!r} describe a left-handed frame")
        return cls(rotation, letters, "body" if letters == "FRD" else "custom")

    @classmethod
    def from_matrix(cls, rotation_from_body: ArrayLike, name: str = "custom") -> Frame:
        """Build a frame from a rotation matrix with ``v_frame = R @ v_body``."""
        return cls(finite_array(rotation_from_body, "rotation_from_body"), name)

    @classmethod
    def stability(
        cls, *, alpha_rad: ArrayLike | None = None, alpha_deg: ArrayLike | None = None
    ) -> Frame:
        """Stability frame: the body frame rotated about y_body by alpha.

        Give exactly one of ``alpha_rad`` and ``alpha_deg``; array angles give a
        batch of frames.
        """
        alpha = _angle_rad(alpha_rad, alpha_deg, "alpha")
        return cls(_stability_from_body(alpha), "stability", "stability")

    @classmethod
    def wind(
        cls,
        *,
        alpha_rad: ArrayLike | None = None,
        alpha_deg: ArrayLike | None = None,
        beta_rad: ArrayLike | None = None,
        beta_deg: ArrayLike | None = None,
    ) -> Frame:
        """Wind frame: the stability frame rotated about z_stability by beta.

        Give exactly one of each angle pair; the alpha and beta arrays broadcast
        together.
        """
        alpha = _angle_rad(alpha_rad, alpha_deg, "alpha")
        beta = _angle_rad(beta_rad, beta_deg, "beta")
        rotation = _wind_from_stability(beta) @ _stability_from_body(alpha)
        return cls(rotation, "wind", "wind")

    @property
    def batch_shape(self) -> tuple[int, ...]:
        """Batch shape of the orientations, without the trailing ``(3, 3)``."""
        return tuple(self.rotation_from_body.shape[:-2])
