from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

# Constantes acústicas exactas
PYTHAGOREAN_COMMA_CENTS: float = 1200.0 * math.log2(((3.0 / 2.0) ** 12) / (2.0 ** 7))  # ~23.4600 c
SYNTONIC_COMMA_CENTS: float = 1200.0 * math.log2(81.0 / 80.0)                         # ~21.5063 c
SCHISMA_CENTS: float = PYTHAGOREAN_COMMA_CENTS - SYNTONIC_COMMA_CENTS                  # ~1.9537 c
PURE_FIFTH_CENTS: float = 1200.0 * math.log2(3.0 / 2.0)                                # ~701.9550 c
PURE_MAJOR_THIRD_CENTS: float = 1200.0 * math.log2(5.0 / 4.0)                          # ~386.3137 c

NOTE_NAMES_SHARP: tuple[str, ...] = (
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"
)

# Proporciones armónicas puras (n: armónico grave, m: armónico agudo) por semitonos
INTERVAL_RATIOS: dict[int, tuple[str, int, int]] = {
    0: ("unison", 1, 1),
    3: ("minor_third", 6, 5),
    4: ("major_third", 5, 4),
    5: ("fourth", 4, 3),
    7: ("fifth", 3, 2),
    8: ("minor_sixth", 8, 5),
    9: ("major_sixth", 5, 3),
    12: ("octave", 2, 1),
}


@dataclass(frozen=True)
class NoteReading:
    midi_note: int
    note_name: str
    octave: int
    full_name: str
    measured_freq: float
    target_freq: float
    cents_diff: float
    comma_ratio: float
    comma_label: str
    in_scale_range: bool


@dataclass(frozen=True)
class BeatResult:
    interval_key: str
    midi_low: int
    midi_high: int
    freq_low: float
    freq_high: float
    harmonic_low: int
    harmonic_high: int
    signed_beats_hz: float
    abs_beats_hz: float
    character: str  # "pure", "narrow", "wide"


def inharmonicity_stretch_cents(midi_note: int, coeff_b: float = 0.0) -> float:
    """
    Calcula el estiramiento de octava en cents respecto a A4 (MIDI 69)
    producido por el coeficiente de inarmonicidad B de la cuerda (Fletcher).
    Para tubos de órgano o cuerdas ideales (coeff_b = 0.0) devuelve 0.0.
    """
    if coeff_b <= 0.0:
        return 0.0
    octaves_from_a4 = (midi_note - 69) / 12.0
    b_local = coeff_b * (2.0 ** (2.0 * octaves_from_a4))
    stretch_per_octave = 600.0 * math.log2((1.0 + 4.0 * b_local) / (1.0 + b_local))
    return octaves_from_a4 * stretch_per_octave


def midi_to_et_freq(midi_note: int, a4_ref: float = 415.0) -> float:
    """Frecuencia base en Temperamento Igual (ET) para una nota MIDI."""
    if a4_ref <= 0.0:
        raise ValueError("La frecuencia de referencia A4 debe ser positiva.")
    return a4_ref * (2.0 ** ((midi_note - 69) / 12.0))


def midi_to_target_freq(
    midi_note: int,
    offsets_cents: Sequence[float],
    a4_ref: float = 415.0,
    inharmonicity_b: float = 0.0,
) -> float:
    """
    Calcula la frecuencia objetivo aplicando el temperamento activo
    y la compensación opcional de inarmonicidad.
    """
    if len(offsets_cents) != 12:
        raise ValueError("El vector de temperamento debe tener exactamente 12 valores.")
    f_et = midi_to_et_freq(midi_note, a4_ref)
    total_offset = offsets_cents[midi_note % 12] + inharmonicity_stretch_cents(
        midi_note, inharmonicity_b
    )
    return f_et * (2.0 ** (total_offset / 1200.0))


def freq_to_cents_diff(measured_freq: float, target_freq: float) -> float:
    """Diferencia logarítmica en cents entre la frecuencia medida y la objetivo."""
    if measured_freq <= 0.0 or target_freq <= 0.0:
        raise ValueError("Las frecuencias deben ser estrictamente positivas.")
    return 1200.0 * math.log2(measured_freq / target_freq)


def cents_to_comma_fraction(
    cents: float, comma_type: str = "syntonic"
) -> tuple[float, str]:
    """
    Convierte una desviación en cents a fracción de coma (sintónica o pitagórica).
    Devuelve (valor_numérico, etiqueta_legible).
    """
    if comma_type == "pythagorean":
        comma_val = PYTHAGOREAN_COMMA_CENTS
        suffix = "CP"
    else:
        comma_val = SYNTONIC_COMMA_CENTS
        suffix = "CS"

    ratio = cents / comma_val
    if abs(ratio) < 0.02:
        return 0.0, f"0 {suffix}"

    # Aproximación a fracciones musicales comunes (1/2, 1/3, 1/4, 1/5, 1/6, 1/8, 1/12)
    common_denoms = (1, 2, 3, 4, 5, 6, 8, 10, 12)
    best_num, best_den = round(ratio), 1
    min_err = abs(ratio - best_num)

    for den in common_denoms:
        num = round(ratio * den)
        if num == 0:
            continue
        err = abs(ratio - (num / den))
        if err < min_err:
            min_err = err
            best_num, best_den = num, den

    if min_err <= 0.035:
        sign = "+" if best_num > 0 else ""
        if best_den == 1:
            label = f"{sign}{best_num} {suffix}"
        else:
            label = f"{sign}{best_num}/{best_den} {suffix}"
    else:
        sign = "+" if ratio > 0 else ""
        label = f"{sign}{ratio:.2f} {suffix}"

    return ratio, label


def midi_note_label(midi_note: int) -> tuple[str, int, str]:
    """Devuelve (nombre_nota, octava, etiqueta_completa) para un número MIDI."""
    name = NOTE_NAMES_SHARP[midi_note % 12]
    octave = (midi_note // 12) - 1
    return name, octave, f"{name}{octave}"


def detect_nearest_note_auto(
    measured_freq: float,
    offsets_cents: Sequence[float],
    a4_ref: float = 415.0,
    inharmonicity_b: float = 0.0,
    comma_type: str = "syntonic",
) -> NoteReading:
    """
    Modo AUTO (escala -50 a +50 cents): encuentra la nota del temperamento
    más cercana a la frecuencia captada.
    """
    approx_midi = int(round(69.0 + 12.0 * math.log2(measured_freq / a4_ref)))
    # Evaluar vecinos por si el offset del temperamento desplaza la frontera de ±50 cents
    candidates = [approx_midi - 1, approx_midi, approx_midi + 1]
    best_midi = min(
        candidates,
        key=lambda m: abs(
            freq_to_cents_diff(
                measured_freq,
                midi_to_target_freq(m, offsets_cents, a4_ref, inharmonicity_b),
            )
        ),
    )

    target_freq = midi_to_target_freq(best_midi, offsets_cents, a4_ref, inharmonicity_b)
    cents = freq_to_cents_diff(measured_freq, target_freq)
    comma_ratio, comma_label = cents_to_comma_fraction(cents, comma_type)
    name, octave, full_name = midi_note_label(best_midi)

    return NoteReading(
        midi_note=best_midi,
        note_name=name,
        octave=octave,
        full_name=full_name,
        measured_freq=measured_freq,
        target_freq=target_freq,
        cents_diff=cents,
        comma_ratio=comma_ratio,
        comma_label=comma_label,
        in_scale_range=abs(cents) <= 50.0,
    )


def evaluate_manual_note(
    measured_freq: float,
    fixed_midi: int,
    offsets_cents: Sequence[float],
    a4_ref: float = 415.0,
    inharmonicity_b: float = 0.0,
    comma_type: str = "syntonic",
) -> NoteReading:
    """
    Modo MANUAL (escala amplia -500 a +500 cents): evalúa la desviación
    respecto a una nota fija seleccionada por el usuario.
    """
    target_freq = midi_to_target_freq(fixed_midi, offsets_cents, a4_ref, inharmonicity_b)
    cents = freq_to_cents_diff(measured_freq, target_freq)
    comma_ratio, comma_label = cents_to_comma_fraction(cents, comma_type)
    name, octave, full_name = midi_note_label(fixed_midi)

    return NoteReading(
        midi_note=fixed_midi,
        note_name=name,
        octave=octave,
        full_name=full_name,
        measured_freq=measured_freq,
        target_freq=target_freq,
        cents_diff=cents,
        comma_ratio=comma_ratio,
        comma_label=comma_label,
        in_scale_range=abs(cents) <= 500.0,
    )


def calibrate_a4_from_measured_note(
    measured_freq: float,
    reference_midi: int,
    offsets_cents: Sequence[float],
    inharmonicity_b: float = 0.0,
) -> float:
    """
    Sugerencia 9.2 (Match Pitch): calcula qué frecuencia base A4 corresponde
    al medir un tubo o cuerda fija de referencia (ej. Principal 4' de órgano)
    bajo el temperamento activo.
    """
    if measured_freq <= 0.0:
        raise ValueError("La frecuencia medida debe ser positiva.")
    if len(offsets_cents) != 12:
        raise ValueError("El vector de temperamento debe tener 12 valores.")

    total_offset = offsets_cents[reference_midi % 12] + inharmonicity_stretch_cents(
        reference_midi, inharmonicity_b
    )
    ratio_from_a4 = (2.0 ** ((reference_midi - 69) / 12.0)) * (
        2.0 ** (total_offset / 1200.0)
    )
    return measured_freq / ratio_from_a4


def calculate_interval_beats(
    midi_low: int,
    midi_high: int,
    offsets_cents: Sequence[float],
    a4_ref: float = 415.0,
    inharmonicity_b: float = 0.0,
) -> BeatResult:
    """
    Calcula la velocidad de batimentos (bat/s) entre dos notas MIDI
    a partir de sus armónicos coincidentes (n * f1 - m * f2).
    """
    semitones = midi_high - midi_low
    if semitones not in INTERVAL_RATIOS:
        raise ValueError(f"Intervalo de {semitones} semitonos no soportado.")

    interval_key, n, m = INTERVAL_RATIOS[semitones]
    f_low = midi_to_target_freq(midi_low, offsets_cents, a4_ref, inharmonicity_b)
    f_high = midi_to_target_freq(midi_high, offsets_cents, a4_ref, inharmonicity_b)

    signed = (n * f_low) - (m * f_high)
    abs_beats = abs(signed)

    if abs_beats < 0.01:
        character = "pure"
    elif signed > 0:
        character = "narrow"
    else:
        character = "wide"

    return BeatResult(
        interval_key=interval_key,
        midi_low=midi_low,
        midi_high=midi_high,
        freq_low=f_low,
        freq_high=f_high,
        harmonic_low=n,
        harmonic_high=m,
        signed_beats_hz=signed,
        abs_beats_hz=abs_beats,
        character=character,
    )
