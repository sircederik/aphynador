from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.acoustics import (
    calculate_interval_beats,
    midi_note_label,
    midi_to_target_freq,
)
from core.temperaments import Temperament


@dataclass
class PartitionStep:
    step_number: int
    target_midi: int
    target_note_label: str
    target_freq_hz: float
    reference_midi: int | None = None
    reference_note_label: str | None = None
    expected_beats_hz: float = 0.0
    interval_character: str = "reference"
    note_es: str = ""
    note_en: str = ""
    completed: bool = False


class PartitionAssistant:
    """
    Asistente interactivo paso a paso para sentar la partición en la octava central.
    Valida automáticamente cada paso cuando la frecuencia medida permanece estable
    dentro de la tolerancia durante `hold_seconds`.
    """

    def __init__(
        self,
        temperament: Temperament,
        a4_ref: float = 415.0,
        inharmonicity_b: float = 0.0,
        tolerance_cents: float = 1.5,
        hold_seconds: float = 1.2,
    ) -> None:
        self.temperament = temperament
        self.a4_ref = a4_ref
        self.inharmonicity_b = inharmonicity_b
        self.tolerance_cents = tolerance_cents
        self.hold_seconds = hold_seconds
        self.steps: list[PartitionStep] = self._build_steps()
        self.current_index: int = 0
        self._stable_elapsed: float = 0.0

    def _build_steps(self) -> list[PartitionStep]:
        raw_seq = self.temperament.partition_sequence
        if not raw_seq:
            # Secuencia cromática estándar A3..G#4 si el temperamento no define una propia
            raw_seq = [{"midi": m} for m in range(57, 69)]

        built: list[PartitionStep] = []
        for idx, item in enumerate(raw_seq, start=1):
            t_midi = int(item["midi"])
            _, _, t_label = midi_note_label(t_midi)
            t_freq = midi_to_target_freq(
                t_midi,
                self.temperament.offsets_cents,
                self.a4_ref,
                self.inharmonicity_b,
            )

            ref_midi = item.get("ref_midi")
            ref_label = None
            beats_hz = 0.0
            char = "reference"

            if ref_midi is not None:
                ref_midi = int(ref_midi)
                _, _, ref_label = midi_note_label(ref_midi)
                low, high = min(t_midi, ref_midi), max(t_midi, ref_midi)
                try:
                    b_res = calculate_interval_beats(
                        low,
                        high,
                        self.temperament.offsets_cents,
                        self.a4_ref,
                        self.inharmonicity_b,
                    )
                    beats_hz = round(b_res.abs_beats_hz, 2)
                    char = b_res.character
                except ValueError:
                    beats_hz = 0.0

            built.append(
                PartitionStep(
                    step_number=idx,
                    target_midi=t_midi,
                    target_note_label=t_label,
                    target_freq_hz=round(t_freq, 2),
                    reference_midi=ref_midi,
                    reference_note_label=ref_label,
                    expected_beats_hz=beats_hz,
                    interval_character=char,
                    note_es=item.get("note_es", ""),
                    note_en=item.get("note_en", ""),
                )
            )
        return built

    @property
    def is_finished(self) -> bool:
        return self.current_index >= len(self.steps)

    @property
    def current_step(self) -> PartitionStep | None:
        if self.is_finished:
            return None
        return self.steps[self.current_index]

    @property
    def stability_progress(self) -> float:
        """Progreso de estabilidad de 0.0 a 1.0 para retroalimentación visual."""
        if self.hold_seconds <= 0.0:
            return 1.0
        return min(1.0, self._stable_elapsed / self.hold_seconds)

    def update(self, cents_diff: float, dt_seconds: float) -> bool:
        """
        Actualiza el estado con la desviación en cents de la nota objetivo actual.
        Devuelve True si el paso actual acaba de completarse.
        """
        step = self.current_step
        if step is None:
            return False

        if abs(cents_diff) <= self.tolerance_cents:
            self._stable_elapsed += max(0.0, dt_seconds)
            if self._stable_elapsed >= self.hold_seconds:
                step.completed = True
                self.current_index += 1
                self._stable_elapsed = 0.0
                return True
        else:
            self._stable_elapsed = 0.0
        return False
