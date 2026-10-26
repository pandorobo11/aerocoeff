"""Shared validation boundary for numeric inputs."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _contains_bool(value: Any) -> bool:
    if isinstance(value, bool | np.bool_):
        return True
    if isinstance(value, np.ndarray):
        return bool(value.dtype == np.bool_)
    if isinstance(value, list | tuple):
        return any(_contains_bool(item) for item in value)
    return False


def finite_array(value: ArrayLike, name: str) -> FloatArray:
    """Return a read-only float64 copy of a finite, real, non-boolean input."""
    if _contains_bool(value):
        raise TypeError(f"{name} must be numeric, not boolean")
    array = np.asarray(value)
    # timedelta64 is an np.integer subtype, but is not a real-number input.
    if array.dtype.kind not in "iuf":
        raise TypeError(f"{name} must be real numeric, got dtype {array.dtype}")
    result = array.astype(np.float64, copy=True)
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite")
    result.flags.writeable = False
    return result


def vector3_array(value: ArrayLike, name: str) -> FloatArray:
    """Return a validated array of 3-vectors with shape ``(..., 3)``."""
    array = finite_array(value, name)
    if array.ndim < 1 or array.shape[-1] != 3:
        raise ValueError(f"{name} must have shape (..., 3), got {array.shape}")
    return array


def positive_scalar(value: ArrayLike, name: str) -> float:
    """Return a validated finite scalar greater than zero."""
    array = finite_array(value, name)
    if array.ndim != 0:
        raise ValueError(f"{name} must be a scalar, got shape {array.shape}")
    scalar = float(array)
    if scalar <= 0.0:
        raise ValueError(f"{name} must be positive, got {scalar}")
    return scalar
