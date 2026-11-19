import math
from pathlib import Path

from core.key_analysis import analyze_temperament_keys
from core.temperaments import TemperamentLibrary
from ui.needle_gauge import BallisticNeedlePhysics, cents_to_normalized


def test_dual_scale_mapping():
    # Escala Auto lineal [-50, +50]
    assert math.isclose(cents_to_normalized(0.0, "auto"), 0.0)
    assert math.isclose(cents_to_normalized(-25.0, "auto"), -0.5)
    assert math.isclose(cents_to_normalized(50.0, "auto"), 1.0)

    # Escala Manual no lineal por tramos [-500, +500]
    assert math.isclose(cents_to_normalized(10.0, "manual"), 0.10)
    assert math.isclose(cents_to_normalized(20.0, "manual"), 0.20)
    assert math.isclose(cents_to_normalized(60.0, "manual"), 0.40)
    assert math.isclose(cents_to_normalized(100.0, "manual"), 0.60)
    assert math.isclose(cents_to_normalized(-300.0, "manual"), -0.80)
    assert math.isclose(cents_to_normalized(500.0, "manual"), 1.00)


def test_ballistic_needle_convergence():
    physics = BallisticNeedlePhysics(stiffness=120.0, damping=20.0, rest_position=-1.0)
    for _ in range(120):
        pos = physics.step(target=0.0, dt=1.0 / 60.0)
    assert math.isclose(pos, 0.0, abs_tol=0.01)


def test_key_harmonic_analysis_detects_wolf_fifth():
    lib = TemperamentLibrary(Path("data/temperaments"))
    mt = lib.get("meantone_quarter_comma")
    keys = analyze_temperament_keys(mt.offsets_cents)

    pure_count = sum(1 for k in keys if k.is_pure_third)
    wolf_keys = [k.key_name for k in keys if k.is_wolf_fifth]

    assert pure_count == 8
    assert wolf_keys == ["G#"]
