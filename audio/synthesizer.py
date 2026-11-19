from __future__ import annotations

from enum import Enum
import threading
import numpy as np


class Waveform(str, Enum):
    SINE = "sine"
    TRIANGLE = "triangle"
    SAWTOOTH = "sawtooth"
    ORGAN_PRINCIPAL = "organ_principal"
    HARPSICHORD = "harpsichord"


class ReferenceSynthesizer:
    """
    Generador de tono de referencia en tiempo real con selector de forma de onda,
    acumulador de fase continuo (sin clics al cambiar de frecuencia) y envolvente
    suave Attack/Release por muestra.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        attack_ms: float = 15.0,
        release_ms: float = 25.0,
    ) -> None:
        self.sample_rate = sample_rate
        self._lock = threading.Lock()
        self._freq_hz: float = 415.0
        self._waveform: Waveform = Waveform.SINE
        self._volume: float = 0.35
        self._enabled: bool = False

        self._phase: float = 0.0
        self._current_gain: float = 0.0
        self._attack_step: float = 1.0 / max(1.0, (attack_ms / 1000.0) * sample_rate)
        self._release_step: float = 1.0 / max(1.0, (release_ms / 1000.0) * sample_rate)

    @property
    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def frequency(self) -> float:
        with self._lock:
            return self._freq_hz

    @property
    def waveform(self) -> Waveform:
        with self._lock:
            return self._waveform

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)

    def set_frequency(self, freq_hz: float) -> None:
        if freq_hz > 0.0:
            with self._lock:
                self._freq_hz = float(freq_hz)

    def set_waveform(self, waveform: Waveform | str) -> None:
        wf = Waveform(waveform)
        with self._lock:
            self._waveform = wf

    def set_volume(self, volume: float) -> None:
        with self._lock:
            self._volume = max(0.0, min(1.0, float(volume)))

    def render_block(self, num_frames: int) -> np.ndarray:
        with self._lock:
            freq = self._freq_hz
            waveform = self._waveform
            target_gain = self._volume if self._enabled else 0.0

        if target_gain == 0.0 and self._current_gain == 0.0:
            return np.zeros(num_frames, dtype=np.float32)

        # Envolvente suave por muestra (evita chasquidos al activar/desactivar)
        env = np.empty(num_frames, dtype=np.float64)
        g = self._current_gain
        for i in range(num_frames):
            if g < target_gain:
                g = min(target_gain, g + self._attack_step)
            elif g > target_gain:
                g = max(target_gain, g - self._release_step)
            env[i] = g
        self._current_gain = g

        # Acumulador de fase continuo en [0, 1)
        phase_inc = freq / self.sample_rate
        phases = (self._phase + np.arange(num_frames, dtype=np.float64) * phase_inc) % 1.0
        self._phase = float((self._phase + num_frames * phase_inc) % 1.0)

        two_pi_p = 2.0 * np.pi * phases

        if waveform == Waveform.SINE:
            wave = np.sin(two_pi_p)
        elif waveform == Waveform.TRIANGLE:
            wave = 2.0 * np.abs(2.0 * phases - 1.0) - 1.0
        elif waveform == Waveform.SAWTOOTH:
            # Diente de sierra limitada en banda (evita aliasing)
            wave = np.zeros(num_frames, dtype=np.float64)
            max_h = min(12, int((self.sample_rate * 0.45) / max(1.0, freq)))
            for h in range(1, max_h + 1):
                wave += ((-1) ** (h + 1)) * np.sin(h * two_pi_p) / h
            wave *= 2.0 / np.pi
        elif waveform == Waveform.ORGAN_PRINCIPAL:
            # Síntesis aditiva: Principal 8' + Octava 4' + Docena + Quincena
            weights = ((1, 1.0), (2, 0.65), (3, 0.25), (4, 0.35), (5, 0.10))
            wave = sum(w * np.sin(h * two_pi_p) for h, w in weights) / 2.35
        elif waveform == Waveform.HARPSICHORD:
            # Síntesis aditiva brillante rica en armónicos agudos para oír batimentos
            weights = ((1, 0.70), (2, 0.90), (3, 0.75), (4, 0.55), (5, 0.40), (6, 0.25))
            wave = sum(w * np.sin(h * two_pi_p) for h, w in weights) / 3.55
        else:
            wave = np.sin(two_pi_p)

        return (wave * env).astype(np.float32)
