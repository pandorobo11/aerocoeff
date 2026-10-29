from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

import aerocoeff.gui
from aerocoeff.gui import pages

APP = Path(aerocoeff.gui.__file__).with_name("app.py")


def _page(name: str) -> AppTest:
    script = f"from aerocoeff.gui.pages import {name}\n{name}()\n"
    return AppTest.from_string(script, default_timeout=30).run()


def _set(app: AppTest, values: Mapping[str, Any]) -> AppTest:
    for key, value in values.items():
        app.number_input(key=key).set_value(value)
    app.run()
    assert not app.exception, app.exception
    return app


def _waiting_for_settings(app: AppTest) -> bool:
    """The case inputs are shown, but no results until the settings are complete."""
    return (
        bool(app.tabs)
        and not app.dataframe
        and any(info.value == pages.SETTINGS_INCOMPLETE for info in app.info)
    )


def _single(app: AppTest) -> dict[str, float]:
    table = app.dataframe[0].value
    return dict(zip(table["Quantity"], table["Value"], strict=True))


class _Upload:
    def __init__(self, text: str) -> None:
        self._data = text.encode()

    def getvalue(self) -> bytes:
        return self._data


@pytest.fixture
def uploads(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    files: dict[str, str] = {}

    def file_uploader(label: str, *args: Any, key: str, **kwargs: Any) -> _Upload | None:
        return _Upload(files[key]) if key in files else None

    monkeypatch.setattr(streamlit, "file_uploader", file_uploader)
    return files


def test_app_opens_on_transform() -> None:
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "Transform"
    assert app.info[0].value == "Enter alpha_deg."


def test_transform_frame_change() -> None:
    # Anderson, Fundamentals of Aerodynamics, Sec. 1.5, at alpha = 30 deg:
    # CD = CN sin(a) + CA cos(a), CL = CN cos(a) - CA sin(a).
    app = _set(
        _page("render_transform"),
        {"transform_case_CA": 0.1, "transform_case_CN": 1.0, "transform_case_alpha_deg": 30.0},
    )
    result = _single(app)
    assert result["CD"] == pytest.approx(0.5866025403784439, rel=1e-15)
    assert result["CL"] == pytest.approx(0.8160254037844386, rel=1e-15)


def test_transform_with_axis_letters_and_errors() -> None:
    app = _page("render_transform")
    app.selectbox(key="transform_columns").select("components").run()
    app.selectbox(key="transform_frame").select("axes").run()
    app.text_input(key="transform_frame_axes").input("BRU").run()
    app.selectbox(key="transform_output").select("body").run()
    # CX_BRU = 1 is a force toward the tail: CX_body = -1, so CA = 1 (axial force).
    result = _single(_set(app, {"transform_case_CX": 1.0}))
    assert result["CA"] == 1.0
    app.text_input(key="transform_frame_axes").input("XYZ").run()
    assert "axes must be three of the letters" in app.error[0].value
    app.number_input(key="transform_reference_area_m2").set_value(0.0).run()
    assert "area_m2 must be positive" in app.error[0].value
    assert _waiting_for_settings(app)


def test_transform_moment_reference_and_reference_quantities() -> None:
    # ADR 0002: CN = 1 moved to a point 0.5 m aft, given in BRU, with l_pitch = 2 m
    # gives Delta Cm = +0.25; with l_pitch' = 0.5 m and S' = S it becomes Cm' = 1.
    app = _page("render_transform")
    app.checkbox(key="transform_change_frame").uncheck().run()
    app.checkbox(key="transform_move").check().run()
    assert app.info[0].value == "Enter the frame of the points."
    assert _waiting_for_settings(app)
    app.text_input(key="transform_points_axes").input("BRU").run()
    values = {
        "transform_reference_length_pitch_m": 2.0,
        "transform_to_x": 0.5,
        "transform_case_CN": 1.0,
    }
    app = _set(app, values)
    assert _single(app)["Cm"] == 0.25
    app.checkbox(key="transform_renormalize").check().run()
    app = _set(app, {"transform_new_reference_length_pitch_m": 0.5})
    assert _single(app)["Cm"] == 1.0
    app.number_input(key="transform_new_reference_area_m2").set_value(-1.0).run()
    assert "area_m2 must be positive" in app.error[0].value
    app.checkbox(key="transform_renormalize").uncheck().run()
    app.checkbox(key="transform_move").uncheck().run()
    assert _single(app)["Cm"] == 0.0


def test_transform_all_changes_together() -> None:
    # As in tests/gui/test_cases.py: CA = 0.1, CN = 1, moved 0.5 m aft (BRU) with
    # l_pitch = 2 m, alpha = 30 deg, then S' = 4 and l_pitch' = 0.5 (S = 2):
    # CD' = 0.5866025 / 2, CL' = 0.8160254 / 2, Cm' = 0.5.
    app = _page("render_transform")
    app.checkbox(key="transform_move").check().run()
    app.checkbox(key="transform_renormalize").check().run()
    app.text_input(key="transform_points_axes").input("BRU").run()
    values = {
        "transform_reference_area_m2": 2.0,
        "transform_reference_length_pitch_m": 2.0,
        "transform_to_x": 0.5,
        "transform_new_reference_area_m2": 4.0,
        "transform_new_reference_length_pitch_m": 0.5,
        "transform_case_CA": 0.1,
        "transform_case_CN": 1.0,
        "transform_case_alpha_deg": 30.0,
    }
    result = _single(_set(app, values))
    assert [result["CD"], result["CL"], result["Cm"]] == pytest.approx(
        [0.5866025403784439 / 2, 0.8160254037844386 / 2, 0.5], rel=1e-14
    )


def test_control_surface_page() -> None:
    # ADR 0003 verification example in BRU: CN_s = 0.1, Ch = -0.04, CB = 0.05.
    app = _page("render_control_surface")
    assert app.info[0].value == "Enter the frame of the points."
    assert _waiting_for_settings(app)
    app.text_input(key="surface_axes").input("BRU").run()
    app.selectbox(key="surface_columns").select("components").run()
    app = _set(
        app,
        {
            "surface_vehicle_reference_area_m2": 2.0,
            "surface_vehicle_reference_length_roll_m": 10.0,
            "surface_vehicle_reference_length_pitch_m": 2.0,
            "surface_vehicle_reference_length_yaw_m": 10.0,
            "surface_hinge_start_x": 5.0,
            "surface_hinge_start_y": 0.2,
            "surface_hinge_end_x": 5.0,
            "surface_hinge_end_y": 1.2,
            "surface_area": 0.2,
            "surface_hinge_length": 0.25,
            "surface_case_CZ": -0.01,
            "surface_case_Cl": -0.0007,
            "surface_case_Cm": -0.0255,
        },
    )
    assert app.info[0].value == "Enter deflection_deg."
    result = _single(_set(app, {"surface_case_deflection_deg": 0.0}))
    assert [result["CN_s"], result["Ch"], result["CB"]] == pytest.approx(
        [0.1, -0.04, 0.05], rel=1e-13
    )
    app.number_input(key="surface_hinge_end_y").set_value(0.2).run()
    assert "must be different points" in app.error[0].value
    assert _waiting_for_settings(app)
    app.number_input(key="surface_hinge_end_y").set_value(1.2).run()
    app.number_input(key="surface_vehicle_reference_area_m2").set_value(0.0).run()
    assert "area_m2 must be positive" in app.error[0].value
    assert _waiting_for_settings(app)


def test_loads_page_in_both_directions() -> None:
    # q S = 1531.25 Pa * 2 m^2 = 3062.5 N (ISA sea level at 50 m/s): CN = 1 gives
    # Fz = -3062.5 N, and the inverse returns CN = 1.
    app = _set(
        _page("render_loads"),
        {
            "loads_reference_area_m2": 2.0,
            "loads_to_case_CN": 1.0,
            "loads_to_case_dynamic_pressure_pa": 1531.25,
        },
    )
    assert _single(app)["Fz_N"] == -3062.5
    app.radio(key="loads_direction").set_value("Forces and moments to coefficients").run()
    app = _set(
        app, {"loads_from_case_Fz_N": -3062.5, "loads_from_case_dynamic_pressure_pa": 1531.25}
    )
    assert _single(app)["CN"] == 1.0
    app.number_input(key="loads_reference_area_m2").set_value(0.0).run()
    assert _waiting_for_settings(app)
    app.radio(key="loads_direction").set_value("Coefficients to forces and moments").run()
    assert _waiting_for_settings(app)


def test_typed_values_survive_an_incomplete_setting() -> None:
    app = _set(
        _page("render_transform"),
        {"transform_case_CA": 0.1, "transform_case_CN": 1.0, "transform_case_alpha_deg": 30.0},
    )
    app.number_input(key="transform_reference_area_m2").set_value(0.0).run()
    assert _waiting_for_settings(app)
    assert app.number_input(key="transform_case_CA").value == 0.1
    app.number_input(key="transform_reference_area_m2").set_value(1.0).run()
    assert _single(app)["CD"] == pytest.approx(0.5866025403784439, rel=1e-15)


def test_csv_batch_waits_for_the_settings(uploads: dict[str, str]) -> None:
    uploads["transform_upload"] = "CA,CY,CN,Cl,Cm,Cn,alpha_deg\n0.1,0,1,0,0,0,30\n"
    app = _page("render_transform")
    assert app.dataframe
    app.number_input(key="transform_reference_area_m2").set_value(0.0).run()
    assert _waiting_for_settings(app)


def test_single_case_calculation_error() -> None:
    app = _set(_page("render_loads"), {"loads_to_case_dynamic_pressure_pa": -1.0})
    assert "dynamic_pressure_pa must be positive" in app.error[0].value


def test_csv_batch(uploads: dict[str, str]) -> None:
    uploads["transform_upload"] = (
        "case,CA,CY,CN,Cl,Cm,Cn,alpha_deg\ncruise,0.1,0,1,0,0,0,30\nclimb,0.1,0,1,0,0,0,90\n"
    )
    app = _page("render_transform")
    assert not app.exception
    table = app.dataframe[0].value
    assert list(table["CD"]) == pytest.approx([0.5866025403784439, 1.0], rel=1e-15)
    assert list(table["CL"]) == pytest.approx([0.8160254037844386, -0.1], abs=1e-15)
    assert len(app.get("download_button")) == 2


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("CA,CY\n1,2\n", "needs the columns"),
        ("CA,CY,CN,Cl,Cm,Cn,alpha_deg\n0,0,0,0,0,0,nan\n", "alpha_deg must be finite"),
    ],
)
def test_csv_batch_errors(uploads: dict[str, str], text: str, message: str) -> None:
    uploads["transform_upload"] = text
    app = _page("render_transform")
    assert message in app.error[0].value
    assert not app.dataframe
