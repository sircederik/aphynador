import math
from pathlib import Path

from core.acoustics import (
    PYTHAGOREAN_COMMA_CENTS,
    SYNTONIC_COMMA_CENTS,
    calculate_interval_beats,
    calibrate_a4_from_measured_note,
    cents_to_comma_fraction,
    detect_nearest_note_auto,
    evaluate_manual_note,
    midi_to_target_freq,
)
from core.climate import ManualClimateProvider
from core.entitlements import EntitlementManager, Feature, Tier
from core.i18n import LocalizationManager
from core.partition import PartitionAssistant
from core.temperaments import (
    TemperamentLibrary,
    build_offsets_from_fifths,
    export_scala_scl,
    import_scala_scl,
)


def test_comma_constants_and_fractions():
    assert math.isclose(PYTHAGOREAN_COMMA_CENTS, 23.46001, abs_tol=1e-4)
    assert math.isclose(SYNTONIC_COMMA_CENTS, 21.50629, abs_tol=1e-4)
    _, label = cents_to_comma_fraction(-SYNTONIC_COMMA_CENTS / 4.0, "syntonic")
    assert label == "-1/4 CS"


def test_auto_and_manual_modes():
    et = [0.0] * 12
    # A415 exacto en modo Auto
    reading_auto = detect_nearest_note_auto(415.0, et, a4_ref=415.0)
    assert reading_auto.full_name == "A4"
    assert math.isclose(reading_auto.cents_diff, 0.0, abs_tol=1e-9)

    # Modo Manual con desviación de -200 cents (un tono abajo de A4 -> G4 = 369.72 Hz)
    g4_freq = midi_to_target_freq(67, et, a4_ref=415.0)
    reading_manual = evaluate_manual_note(g4_freq, fixed_midi=69, offsets_cents=et, a4_ref=415.0)
    assert reading_manual.full_name == "A4"
    assert math.isclose(reading_manual.cents_diff, -200.0, abs_tol=1e-6)
    assert reading_manual.in_scale_range is True


def test_match_pitch_calibration_and_inharmonicity():
    lib = TemperamentLibrary(Path("data/temperaments"))
    w3 = lib.get("werckmeister_iii")

    # Simular medición de C4 en un órgano a A4 = 418.4 Hz con leve inarmonicidad
    measured_c4 = midi_to_target_freq(60, w3.offsets_cents, a4_ref=418.4, inharmonicity_b=0.00015)
    calibrated_a4 = calibrate_a4_from_measured_note(
        measured_c4, reference_midi=60, offsets_cents=w3.offsets_cents, inharmonicity_b=0.00015
    )
    assert math.isclose(calibrated_a4, 418.4, rel_tol=1e-12)


def test_beat_rate_calculations():
    lib = TemperamentLibrary(Path("data/temperaments"))
    mt = lib.get("meantone_quarter_comma")
    # En mesotónico 1/4 coma, la tercera mayor C4-E4 es pura (~0 bat/s)
    beats = calculate_interval_beats(60, 64, mt.offsets_cents, a4_ref=415.0)
    assert beats.abs_beats_hz < 0.05


def test_scala_roundtrip_and_fifths_builder(tmp_path: Path):
    lib = TemperamentLibrary(Path("data/temperaments"))
    w3 = lib.get("werckmeister_iii")
    scl_file = tmp_path / "w3_export.scl"
    export_scala_scl(w3, scl_file)
    imported = import_scala_scl(scl_file)
    for orig, imp in zip(w3.offsets_cents, imported.offsets_cents):
        assert math.isclose(orig, imp, abs_tol=1e-3)

    # Validar constructor desde círculo de quintas para Vallotti
    val_offsets = build_offsets_from_fifths(
        up_fifths_tempering=[
            ("pythagorean", -1 / 6),  # C-G
            ("pythagorean", -1 / 6),  # G-D
            ("pythagorean", -1 / 6),  # D-A
            ("pythagorean", -1 / 6),  # A-E
            ("pythagorean", -1 / 6),  # E-B
            ("pure", 0.0),            # B-F#
            ("pure", 0.0),            # F#-C#
            ("pure", 0.0),            # C#-G#
        ],
        down_fifths_tempering=[
            ("pythagorean", -1 / 6),  # C-F
            ("pure", 0.0),            # F-Bb
            ("pure", 0.0),            # Bb-Eb
        ],
    )
    assert math.isclose(val_offsets[5], 1.96, abs_tol=0.02)


def test_partition_assistant_progression():
    lib = TemperamentLibrary(Path("data/temperaments"))
    w3 = lib.get("werckmeister_iii")
    assistant = PartitionAssistant(w3, a4_ref=415.0, tolerance_cents=1.5, hold_seconds=1.0)

    assert assistant.current_step.target_midi == 60
    assert assistant.update(cents_diff=0.5, dt_seconds=0.6) is False
    assert assistant.update(cents_diff=0.4, dt_seconds=0.5) is True
    assert assistant.current_step.target_midi == 67


def test_i18n_entitlements_and_climate():
    i18n = LocalizationManager(Path("data/locales"))
    assert "Aphynador" in i18n.t("app.title")
    i18n.set_language("en")
    assert "Historical Tuner" in i18n.t("app.title")

    free_mgr = EntitlementManager(Tier.FREE)
    assert free_mgr.can_use(Feature.BASIC_TUNER) is True
    assert free_mgr.can_use(Feature.SCALA_IMPORT_EXPORT) is False

    pro_mgr = EntitlementManager(Tier.PRO)
    assert pro_mgr.can_use(Feature.SCALA_IMPORT_EXPORT) is True

    climate = ManualClimateProvider(temperature_c=19.5, humidity_pct=54.0)
    assert climate.get_current_reading().humidity_pct == 54.0
