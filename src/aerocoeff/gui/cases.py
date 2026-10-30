"""Case tables, input choices, and calculations behind the GUI pages.

A case table maps column names to one value per case, so a single case and a CSV
batch go through the same code. Every calculation calls the public API; this
module adds no formula of its own and does not import Streamlit.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from aerocoeff._validation import FloatArray
from aerocoeff.coefficients import AeroCoefficients, ReferenceQuantities
from aerocoeff.control_surface import ControlSurface
from aerocoeff.frames import Frame

Columns = dict[str, FloatArray]
"""Column name to a ``(n,)`` array with one value per case."""

ColumnSet = Literal["axial_normal", "lift_drag", "components"]
FrameChoiceKind = Literal["body", "stability", "wind", "axes"]

ALPHA = "alpha_deg"
BETA = "beta_deg"
DEFLECTION = "deflection_deg"
DYNAMIC_PRESSURE = "dynamic_pressure_pa"

COEFFICIENT_COLUMNS: dict[ColumnSet, tuple[str, ...]] = {
    "axial_normal": ("CA", "CY", "CN", "Cl", "Cm", "Cn"),
    "lift_drag": ("CD", "CY", "CL", "Cl", "Cm", "Cn"),
    "components": ("CX", "CY", "CZ", "Cl", "Cm", "Cn"),
}
LOAD_COLUMNS = ("Fx_N", "Fy_N", "Fz_N", "Mx_Nm", "My_Nm", "Mz_Nm")
HINGE_COLUMNS = ("CX_h", "CY_h", "CZ_h", "Cl_h", "Cm_h", "Cn_h")
OUTPUT_SUFFIX = "_out"
"""Appended to a result column name until no other column of the CSV has it."""


@dataclass(frozen=True)
class FrameChoice:
    """A frame as chosen in the GUI; stability and wind take their angles per case."""

    kind: FrameChoiceKind
    axes: str = "FRD"

    @property
    def angle_columns(self) -> tuple[str, ...]:
        """Case columns that this frame needs."""
        if self.kind == "stability":
            return (ALPHA,)
        if self.kind == "wind":
            return (ALPHA, BETA)
        return ()

    def build(self, cases: Mapping[str, FloatArray]) -> Frame:
        """Return the frame for every case."""
        if self.kind == "body":
            return Frame.body()
        if self.kind == "stability":
            return Frame.stability(alpha_deg=cases[ALPHA])
        if self.kind == "wind":
            return Frame.wind(alpha_deg=cases[ALPHA], beta_deg=cases[BETA])
        return Frame.from_axes(self.axes)


@dataclass(frozen=True)
class CoefficientInput:
    """Which six coefficient columns are given and in which frame.

    ``CA, CY, CN`` are in the body frame and ``CD, CY, CL`` in the stability frame;
    ``frame`` is used only for frame components ``CX, CY, CZ``.
    """

    column_set: ColumnSet
    frame: FrameChoice = field(default_factory=lambda: FrameChoice("body"))

    @property
    def frame_choice(self) -> FrameChoice:
        """Frame of the given coefficients."""
        if self.column_set == "axial_normal":
            return FrameChoice("body")
        if self.column_set == "lift_drag":
            return FrameChoice("stability")
        return self.frame

    @property
    def required_columns(self) -> tuple[str, ...]:
        """Coefficient columns followed by the angle columns of the input frame."""
        return COEFFICIENT_COLUMNS[self.column_set] + self.frame_choice.angle_columns

    def build(
        self, cases: Mapping[str, FloatArray], reference: ReferenceQuantities
    ) -> AeroCoefficients:
        """Return the coefficients of every case."""
        values = np.stack([cases[name] for name in COEFFICIENT_COLUMNS[self.column_set]], -1)
        if self.column_set == "axial_normal":
            return AeroCoefficients.from_axial_normal_array(values, reference=reference)
        if self.column_set == "lift_drag":
            return AeroCoefficients.from_lift_drag_array(
                values, reference=reference, alpha_deg=cases[ALPHA]
            )
        return AeroCoefficients.from_components_array(
            values, reference=reference, frame=self.frame.build(cases)
        )


@dataclass(frozen=True)
class PointTransfer:
    """Old and new moment reference points, in meters in the ``points_axes`` frame."""

    from_point_m: tuple[float, float, float]
    to_point_m: tuple[float, float, float]
    points_axes: str


def _merged(*groups: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(name for group in groups for name in group))


def _case_count(cases: Mapping[str, FloatArray]) -> int:
    return len(next(iter(cases.values())))


def coefficient_columns(coefficients: AeroCoefficients, count: int) -> Columns:
    """Frame components, plus ``CA, CN`` in body axes or ``CD, CL`` in stability axes."""
    names = ["CX", "CY", "CZ", "Cl", "Cm", "Cn"]
    if coefficients.frame.kind == "body":
        names += ["CA", "CN"]
    elif coefficients.frame.kind == "stability":
        names += ["CD", "CL"]
    return {name: np.broadcast_to(getattr(coefficients, name), (count,)) for name in names}


def transform_columns(source: CoefficientInput, target: FrameChoice | None) -> tuple[str, ...]:
    """Case columns of :func:`transform_cases`."""
    return _merged(source.required_columns, () if target is None else target.angle_columns)


def transform_cases(
    source: CoefficientInput,
    cases: Mapping[str, FloatArray],
    reference: ReferenceQuantities,
    *,
    target: FrameChoice | None,
    transfer: PointTransfer | None,
    new_reference: ReferenceQuantities | None,
) -> Columns:
    """Change the frame, the moment reference point, and the reference quantities.

    Each change is optional; without ``target`` the results stay in the input frame.
    ``new_reference`` lengths belong to the axes of the output frame.
    """
    coefficients = source.build(cases, reference).transform(
        frame=None if target is None else target.build(cases),
        reference=new_reference,
        from_point_m=None if transfer is None else transfer.from_point_m,
        to_point_m=None if transfer is None else transfer.to_point_m,
        points_frame=None if transfer is None else Frame.from_axes(transfer.points_axes),
    )
    return coefficient_columns(coefficients, _case_count(cases))


def surface_columns(source: CoefficientInput) -> tuple[str, ...]:
    """Case columns of :func:`surface_components`."""
    return _merged(source.required_columns, (DEFLECTION,))


def surface_components(
    source: CoefficientInput,
    cases: Mapping[str, FloatArray],
    reference: ReferenceQuantities,
    surface: ControlSurface,
    moment_reference_m: tuple[float, float, float],
) -> Columns:
    """``CN_s, Ch, CB`` and the six components in the hinge frame for every case."""
    loads = surface.loads(
        source.build(cases, reference),
        moment_reference_m=moment_reference_m,
        deflection_deg=cases[DEFLECTION],
    )
    count = _case_count(cases)
    hinge = loads.to_components_array()
    columns = {
        "CN_s": np.broadcast_to(loads.CZ, (count,)),
        "Ch": np.broadcast_to(loads.Cm, (count,)),
        "CB": np.broadcast_to(loads.Cl, (count,)),
    }
    for index, name in enumerate(HINGE_COLUMNS):
        columns[name] = np.broadcast_to(hinge[..., index], (count,))
    return columns


def loads_columns(source: CoefficientInput) -> tuple[str, ...]:
    """Case columns of :func:`coefficients_to_loads`."""
    return _merged(source.required_columns, (DYNAMIC_PRESSURE,))


def coefficients_to_loads(
    source: CoefficientInput, cases: Mapping[str, FloatArray], reference: ReferenceQuantities
) -> Columns:
    """Forces in N and moments in N m along and about the axes of the input frame."""
    coefficients = source.build(cases, reference)
    loads = coefficients.to_loads_array(dynamic_pressure_pa=cases[DYNAMIC_PRESSURE])
    count = _case_count(cases)
    return {
        name: np.broadcast_to(loads[..., index], (count,))
        for index, name in enumerate(LOAD_COLUMNS)
    }


def coefficient_from_loads_columns(frame: FrameChoice) -> tuple[str, ...]:
    """Case columns of :func:`loads_to_coefficients`."""
    return _merged(LOAD_COLUMNS, frame.angle_columns, (DYNAMIC_PRESSURE,))


def loads_to_coefficients(
    frame: FrameChoice, cases: Mapping[str, FloatArray], reference: ReferenceQuantities
) -> Columns:
    """Coefficients from forces and moments given along and about the axes of ``frame``."""
    values = np.stack([cases[name] for name in LOAD_COLUMNS], -1)
    coefficients = AeroCoefficients.from_loads_array(
        values,
        dynamic_pressure_pa=cases[DYNAMIC_PRESSURE],
        reference=reference,
        frame=frame.build(cases),
    )
    return coefficient_columns(coefficients, _case_count(cases))


@dataclass(frozen=True)
class CaseTable:
    """Cases read from a CSV file: every column as text, the required ones as numbers."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    values: Columns


def read_cases_csv(data: bytes | str, required: Sequence[str]) -> CaseTable:
    """Read a CSV file with a header row; extra columns are kept for the output.

    Errors name the file line on which the record starts.
    """
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
    reader = csv.reader(io.StringIO(text))
    # Each record with the file line it starts on; blank lines are skipped.
    records: list[tuple[int, list[str]]] = []
    start = 1
    for record in reader:
        if any(cell.strip() for cell in record):
            records.append((start, record))
        start = reader.line_num + 1
    if not records:
        raise ValueError("the CSV file is empty")
    header = tuple(name.strip() for name in records[0][1])
    if len(set(header)) != len(header):
        raise ValueError("the CSV header repeats a column name")
    missing = [name for name in required if name not in header]
    if missing:
        raise ValueError(f"the CSV file needs the columns: {', '.join(missing)}")
    lines = [line for line, _ in records[1:]]
    rows = tuple(tuple(cell.strip() for cell in row) for _, row in records[1:])
    if not rows:
        raise ValueError("the CSV file has no data rows")
    for line, row in zip(lines, rows, strict=True):
        if len(row) != len(header):
            raise ValueError(f"line {line} has {len(row)} values, expected {len(header)}")
    values: Columns = {}
    for name in required:
        index = header.index(name)
        column = np.empty(len(rows))
        for case, (line, row) in enumerate(zip(lines, rows, strict=True)):
            try:
                column[case] = float(row[index])
            except ValueError:
                raise ValueError(
                    f"line {line}, column {name}: {row[index]!r} is not a number"
                ) from None
        values[name] = column
    return CaseTable(header, rows, values)


def cases_csv_template(required: Sequence[str]) -> str:
    """A CSV file with the required header and no data rows."""
    return ",".join(required) + "\n"


def write_results_csv(table: CaseTable, results: Columns) -> str:
    """The input columns followed by the results.

    A result name that is already taken gets :data:`OUTPUT_SUFFIX` until it is unique.
    """
    taken = set(table.header)
    names = []
    for name in results:
        while name in taken:
            name += OUTPUT_SUFFIX
        taken.add(name)
        names.append(name)
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow([*table.header, *names])
    for index, row in enumerate(table.rows):
        writer.writerow([*row, *(repr(float(column[index])) for column in results.values())])
    return stream.getvalue()


def single_case(values: Mapping[str, float]) -> Columns:
    """A case table with one case."""
    return {name: np.array([value], dtype=np.float64) for name, value in values.items()}
