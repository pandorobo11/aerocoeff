import math

import numpy as np
import pytest

from aerocoeff._validation import finite_array, positive_scalar, vector3_array


def test_finite_array_converts_integers_to_read_only_float64() -> None:
    source = np.array([1, 2, 3])
    result = finite_array(source, "x")
    assert result.dtype == np.float64
    np.testing.assert_array_equal(result, [1.0, 2.0, 3.0])
    assert not result.flags.writeable
    source[0] = 10
    assert result[0] == 1.0


@pytest.mark.parametrize(
    "value",
    [True, np.bool_(False), [1.0, True], ((1.0,), (False,)), np.array([True, False])],
)
def test_finite_array_rejects_booleans(value: object) -> None:
    with pytest.raises(TypeError, match="boolean"):
        finite_array(value, "x")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [
        "1.0",
        [1 + 2j],
        np.array([object()]),
        np.timedelta64(1, "s"),
        np.timedelta64("NaT", "ns"),
        np.array([1, 2, 3], dtype="timedelta64[D]"),
        np.array([1, "NaT"], dtype="timedelta64[ns]"),
        np.datetime64("2026-10-26"),
        np.datetime64("NaT", "ns"),
    ],
)
def test_finite_array_rejects_non_real_values(value: object) -> None:
    with pytest.raises(TypeError, match="real numeric"):
        finite_array(value, "x")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [math.nan, [0.0, math.inf], -math.inf])
def test_finite_array_rejects_non_finite_values(value: object) -> None:
    with pytest.raises(ValueError, match="finite"):
        finite_array(value, "x")  # type: ignore[arg-type]


def test_vector3_array_accepts_batches() -> None:
    assert vector3_array(np.zeros((4, 2, 3)), "v").shape == (4, 2, 3)


@pytest.mark.parametrize("value", [1.0, [1.0, 2.0], np.zeros((3, 2))])
def test_vector3_array_rejects_wrong_shapes(value: object) -> None:
    with pytest.raises(ValueError, match=r"\(\.\.\., 3\)"):
        vector3_array(value, "v")  # type: ignore[arg-type]


def test_positive_scalar_returns_float() -> None:
    result = positive_scalar(np.int64(2), "s")
    assert result == 2.0
    assert isinstance(result, float)


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_positive_scalar_rejects_non_positive_values(value: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        positive_scalar(value, "s")


def test_positive_scalar_rejects_arrays() -> None:
    with pytest.raises(ValueError, match="scalar"):
        positive_scalar([1.0], "s")
