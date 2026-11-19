import math
import numpy as np

from audio.detector import PitchResult, PitchStabilizer, YinPitchDetector
from audio.engine import DuplexAudioEngine
from audio.synthesizer import ReferenceSynthesizer, Waveform


def _make_harmonic_tone(freq_hz: float, sample_rate: int = 44100, frames: int = 4096) -> np.ndarray:
    t = np.arange(frames, dtype=np.float64) / sample_rate
    # Simula clavecín/órgano donde el 2.º y 3.º armónico superan a la fundamental
    return (
        0.35 * np.sin(2.0 * np.pi * freq_hz * t)
        + 0.85 * np.sin(2.0 * np.pi * 2.0 * freq_hz * t + 0.3)
        + 0.60 * np.sin(2.0 * np.pi * 3.0 * freq_hz * t + 1.1)
        + 0.25 * np.sin(2.0 * np.pi * 4.0 * freq_hz * t)
    )


def test_yin_precision_and_harmonic_immunity():
    sr = 44100
    detector = YinPitchDetector(sample_rate=sr, lowpass_cutoff_hz=2000.0)

    for f_true in (65.406, 110.0, 246.76, 415.0, 440.0, 880.0):
        signal = _make_harmonic_tone(f_true, sample_rate=sr, frames=4096)
        res = detector.detect(signal)
        assert res.freq_hz > 0.0
        assert res.confidence > 0.90
        cents_err = abs(1200.0 * math.log2(res.freq_hz / f_true))
        assert cents_err < 0.5, f"Error excesivo en {f_true} Hz: {cents_err:.3f} c"


def test_yin_rejects_silence_and_low_noise():
    detector = YinPitchDetector(sample_rate=44100, noise_floor_rms=0.005)
    silence = np.zeros(4096, dtype=np.float32)
    res_silent = detector.detect(silence)
    assert res_silent.freq_hz == 0.0

    rng = np.random.default_rng(42)
    quiet_noise = rng.normal(0.0, 0.0005, 4096).astype(np.float32)
    res_noise = detector.detect(quiet_noise)
    assert res_noise.freq_hz == 0.0


def test_pitch_stabilizer_filters_octave_glitch():
    stabilizer = PitchStabilizer(window_size=3, min_confidence=0.65)
    r1 = stabilizer.update(PitchResult(415.0, 0.98, 0.2, 1.0))
    r2 = stabilizer.update(PitchResult(830.0, 0.90, 0.2, 1.1))  # Salto transitorio de octava
    r3 = stabilizer.update(PitchResult(415.1, 0.98, 0.2, 1.2))
    assert math.isclose(r3.freq_hz, 415.1, abs_tol=0.2)
    assert r1.freq_hz == 415.0 and r2.freq_hz > 0.0


def test_synthesizer_phase_continuity_and_waveforms():
    sr = 44100
    synth = ReferenceSynthesizer(sample_rate=sr, attack_ms=10.0, release_ms=15.0)
    synth.set_enabled(True)
    synth.set_volume(0.5)
    synth.set_frequency(415.0)

    block1 = synth.render_block(1024)
    synth.set_frequency(440.0)
    block2 = synth.render_block(1024)

    # Transición de fase continua sin saltos bruscos (clics)
    boundary_jump = abs(float(block2[0]) - float(block1[-1]))
    assert boundary_jump < 0.05

    # Comprobar presencia de armónicos en modo Clavecín vs Senoidal
    synth.set_waveform(Waveform.HARPSICHORD)
    harp_block = synth.render_block(4096)
    spectrum = np.abs(np.fft.rfft(harp_block * np.hanning(len(harp_block))))
    freqs = np.fft.rfftfreq(len(harp_block), 1.0 / sr)
    fund_amp = spectrum[np.argmin(np.abs(freqs - 440.0))]
    harm2_amp = spectrum[np.argmin(np.abs(freqs - 880.0))]
    assert harm2_amp > fund_amp * 0.8


def test_duplex_engine_headless_cycle():
    engine = DuplexAudioEngine(sample_rate=44100, block_size=4096)
    engine.synthesizer.set_waveform(Waveform.ORGAN_PRINCIPAL)
    engine.synthesizer.set_frequency(415.0)
    engine.synthesizer.set_enabled(True)

    mic_signal = _make_harmonic_tone(415.0, sample_rate=44100, frames=4096)
    out = engine.process_block(mic_signal, 4096, timestamp=10.0)
    snap = engine.get_snapshot()

    assert len(out) == 4096
    assert np.max(np.abs(out)) > 0.05
    assert math.isclose(snap.pitch.freq_hz, 415.0, abs_tol=0.3)
    assert snap.synth_enabled is True
    assert snap.synth_waveform == Waveform.ORGAN_PRINCIPAL
