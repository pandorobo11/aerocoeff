import dataclasses

import numpy as np
import pytest

from aerocoeff import AeroCoefficients, Frame, ReferenceQuantities

REFERENCE = ReferenceQuantities(
    area_m2=2.0, length_roll_m=4.0, length_pitch_m=0.5, length_yaw_m=4.0
)


def test_reference_quantities_store_floats() -> None:
    reference = ReferenceQuantities(2, 4, 0.5, 4)
    assert reference == REFERENCE
    assert isinstance(reference.area_m2, float)
    np.testing.assert_array_equal(reference.moment_lengths_m, [4.0, 0.5, 4.0])
    assert not reference.moment_lengths_m.flags.writeable


def test_reference_quantities_from_span_chord() -> None:
    # Convention in ADR 0001: l_roll = l_yaw = b and l_pitch = c.
    assert ReferenceQuantities.from_span_chord(area_m2=2.0, span_m=4.0, chord_m=0.5) == REFERENCE


@pytest.mark.parametrize("field", ["area_m2", "length_roll_m", "length_pitch_m", "length_yaw_m"])
@pytest.mark.parametrize(
    ("value", "error"), [(0.0, ValueError), (-1.0, ValueError), (True, TypeError)]
)
def test_reference_quantities_reject_invalid_values(
    field: str, value: float, error: type[Exception]
) -> None:
    with pytest.raises(error, match=field):
        dataclasses.replace(REFERENCE, **{field: value})


def test_reference_quantities_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        REFERENCE.area_m2 = 3.0  # type: ignore[misc]


def test_from_components_defaults_to_body_frame() -> None:
    coefficients = AeroCoefficients.from_components(
        CX=-0.1, CY=0.02, CZ=-0.8, Cl=0.001, Cm=-0.05, Cn=0.003, reference=REFERENCE
    )
    assert coefficients.frame.name == "FRD"
    np.testing.assert_array_equal(coefficients.force, [-0.1, 0.02, -0.8])
    np.testing.assert_array_equal(coefficients.moment, [0.001, -0.05, 0.003])
    np.testing.assert_array_equal(
        [coefficients.CX, coefficients.CY, coefficients.CZ], [-0.1, 0.02, -0.8]
    )
    np.testing.assert_array_equal(
        [coefficients.Cl, coefficients.Cm, coefficients.Cn], [0.001, -0.05, 0.003]
    )


def test_from_components_broadcasts_components() -> None:
    coefficients = AeroCoefficients.from_components(
        CX=[0.1, 0.2, 0.3], CY=0, CZ=-1, Cl=0, Cm=[[0.0], [0.1]], Cn=0, reference=REFERENCE
    )
    assert coefficients.force.shape == (2, 3, 3)
    np.testing.assert_array_equal(coefficients.CX[1], [0.1, 0.2, 0.3])
    np.testing.assert_array_equal(coefficients.Cm[:, 0], [0.0, 0.1])


def test_from_components_keeps_an_explicit_frame() -> None:
    frame = Frame.from_axes("BRU")
    coefficients = AeroCoefficients.from_components(
        CX=0, CY=0, CZ=0, Cl=0, Cm=0, Cn=0, reference=REFERENCE, frame=frame
    )
    assert coefficients.frame is frame


def test_from_components_rejects_non_finite_values_by_name() -> None:
    with pytest.raises(ValueError, match="Cn must be finite"):
        AeroCoefficients.from_components(
            CX=0, CY=0, CZ=0, Cl=0, Cm=0, Cn=np.nan, reference=REFERENCE
        )


def test_coefficients_are_read_only() -> None:
    coefficients = AeroCoefficients(np.zeros(3), np.zeros(3), Frame.body(), REFERENCE)
    with pytest.raises(ValueError, match="read-only"):
        coefficients.force[0] = 1.0


def test_force_and_moment_shapes_must_match() -> None:
    with pytest.raises(ValueError, match="same shape"):
        AeroCoefficients(np.zeros((2, 3)), np.zeros(3), Frame.body(), REFERENCE)


def test_frame_batch_must_broadcast_with_coefficients() -> None:
    frame = Frame.from_matrix(np.broadcast_to(np.eye(3), (4, 3, 3)))
    AeroCoefficients(np.zeros((2, 4, 3)), np.zeros((2, 4, 3)), frame, REFERENCE)
    with pytest.raises(ValueError, match="does not broadcast"):
        AeroCoefficients(np.zeros((2, 3)), np.zeros((2, 3)), frame, REFERENCE)


def test_frame_and_reference_types_are_checked() -> None:
    with pytest.raises(TypeError, match="Frame"):
        AeroCoefficients(np.zeros(3), np.zeros(3), "FRD", REFERENCE)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ReferenceQuantities"):
        AeroCoefficients(np.zeros(3), np.zeros(3), Frame.body(), 1.0)  # type: ignore[arg-type]
