"""Coordinate frames defined by their orientation relative to the body frame.

Conventions follow ADR 0001: the body frame is FRD (x forward, y toward the right
wing, z down), every frame is right-handed, and a frame is stored as the rotation
``R`` with ``v_frame = R @ v_body``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from aerocoeff._validation import FloatArray, finite_array

ROTATION_ATOL = 1e-9
"""Absolute tolerance for orthonormality and determinant checks of rotations."""

_DIRECTIONS_BODY: dict[str, tuple[float, float, float]] = {
    "F": (1.0, 0.0, 0.0),
    "B": (-1.0, 0.0, 0.0),
    "R": (0.0, 1.0, 0.0),
    "L": (0.0, -1.0, 0.0),
    "D": (0.0, 0.0, 1.0),
    "U": (0.0, 0.0, -1.0),
}
_OPPOSITE_PAIRS = ("FB", "RL", "DU")


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


@dataclass(frozen=True, eq=False)
class Frame:
    """A right-handed frame given by ``rotation_from_body`` (``v_frame = R @ v_body``).

    ``rotation_from_body`` has shape ``(..., 3, 3)`` so that one frame object can
    describe a batch of orientations.
    """

    rotation_from_body: FloatArray
    name: str

    def __post_init__(self) -> None:
        rotation = _validated_rotation(self.rotation_from_body, "rotation_from_body")
        object.__setattr__(self, "rotation_from_body", rotation)
        if not isinstance(self.name, str) or not self.name:
            raise TypeError("name must be a non-empty string")

    @classmethod
    def body(cls) -> Frame:
        """The default body frame, FRD."""
        return cls.from_axes("FRD")

    @classmethod
    def from_axes(cls, axes: str) -> Frame:
        """Build a frame from three body-direction letters for its x, y, and z axes.

        Letters are F/B (forward/back), R/L (right/left wing), and D/U (down/up),
        one from each pair, in any order. For example, ``"FRD"`` is the body frame
        and ``"BRU"`` is the panelsolver STL frame.
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
        return cls(rotation, letters)

    @classmethod
    def from_matrix(cls, rotation_from_body: ArrayLike, name: str = "custom") -> Frame:
        """Build a frame from a rotation matrix with ``v_frame = R @ v_body``."""
        return cls(finite_array(rotation_from_body, "rotation_from_body"), name)

    @property
    def batch_shape(self) -> tuple[int, ...]:
        """Batch shape of the orientations, without the trailing ``(3, 3)``."""
        return tuple(self.rotation_from_body.shape[:-2])
