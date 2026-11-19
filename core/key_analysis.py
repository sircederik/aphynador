from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.acoustics import PURE_FIFTH_CENTS, PURE_MAJOR_THIRD_CENTS

KEY_NAMES_DISPLAY: tuple[str, ...] = (
    "C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"
)


@dataclass(frozen=True)
class KeyQuality:
    root_pc: int
    key_name: str
    major_third_cents: float
    major_third_err_from_pure: float
    fifth_cents: float
    fifth_err_from_pure: float
    is_pure_third: bool
    is_wolf_fifth: bool


def analyze_temperament_keys(offsets_cents: Sequence[float]) -> list[KeyQuality]:
    """
    Evalúa las 12 tríadas mayores de un temperamento respecto a la tercera mayor
    acústica pura (5/4 = 386.31 c) y la quinta pura (3/2 = 701.96 c).
    """
    if len(offsets_cents) != 12:
        raise ValueError("Se requieren exactamente 12 offsets en cents.")

    results: list[KeyQuality] = []
    for root in range(12):
        third = (root + 4) % 12
        fifth = (root + 7) % 12

        m3_size = (400.0 + offsets_cents[third] - offsets_cents[root]) % 1200.0
        fifth_size = (700.0 + offsets_cents[fifth] - offsets_cents[root]) % 1200.0

        m3_err = m3_size - PURE_MAJOR_THIRD_CENTS
        fifth_err = fifth_size - PURE_FIFTH_CENTS

        results.append(
            KeyQuality(
                root_pc=root,
                key_name=KEY_NAMES_DISPLAY[root],
                major_third_cents=round(m3_size, 2),
                major_third_err_from_pure=round(m3_err, 2),
                fifth_cents=round(fifth_size, 2),
                fifth_err_from_pure=round(fifth_err, 2),
                is_pure_third=abs(m3_err) <= 2.5,
                is_wolf_fifth=abs(fifth_err) >= 15.0,
            )
        )
    return results
