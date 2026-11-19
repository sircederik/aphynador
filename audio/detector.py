from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import statistics
import time
import numpy as np


@dataclass(frozen=True)
class PitchResult:
    freq_hz: float
    confidence: float
    rms: float
    timestamp: float


class YinPitchDetector:
    """
    Detector de frecuencia fundamental (f0) basado en el algoritmo YIN
    (de Cheveigné & Kawahara) con interpolación parabólica sub-muestra
    y filtro paso-bajo opcional para instrumentos ricos en armónicos.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        f_min: float = 40.0,
        f_max: float = 3500.0,
        threshold: float = 0.15,
        noise_floor_rms: float = 0.005,
        lowpass_cutoff_hz: float | None = 1800.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.f_min = f_min
        self.f_max = f_max
        self.threshold = threshold
        self.noise_floor_rms = noise_floor_rms
        self.lowpass_cutoff_hz = lowpass_cutoff_hz

    def _apply_lowpass(self, x: np.ndarray) -> np.ndarray:
        if self.lowpass_cutoff_hz is None or self.lowpass_cutoff_hz <= 0.0:
            return x
        rc = 1.0 / (2.0 * np.pi * self.lowpass_cutoff_hz)
        dt = 1.0 / self.sample_rate
        alpha = dt / (rc + dt)
        y = np.empty_like(x)
        acc = float(x[0])
        y[0] = acc
        one_minus_alpha = 1.0 - alpha
        for i in range(1, len(x)):
            acc = acc + alpha * (float(x[i]) - acc)
            y[i] = acc
        return y

    def detect(self, signal: np.ndarray, timestamp: float | None = None) -> PitchResult:
        now = time.monotonic() if timestamp is None else timestamp
        if signal.ndim > 1:
            mono = np.mean(signal, axis=1, dtype=np.float64)
        else:
            mono = signal.astype(np.float64, copy=False)

        if len(mono) < 64:
            return PitchResult(0.0, 0.0, 0.0, now)

        # Eliminación de componente continua (DC offset)
        x = mono - np.mean(mono)
        rms = float(np.sqrt(np.mean(x * x)))
        if rms < self.noise_floor_rms:
            return PitchResult(0.0, 0.0, rms, now)

        x = self._apply_lowpass(x)

        n = len(x)
        tau_min = max(2, int(self.sample_rate / self.f_max))
        tau_max = min(n // 2, int(self.sample_rate / self.f_min))
        if tau_max <= tau_min + 2:
            return PitchResult(0.0, 0.0, rms, now)

        # Función de diferencia exacta d(tau) mediante correlación cruzada FFT
        w = n - tau_max
        fft_size = 1 << (n - 1).bit_length()
        x_first = np.zeros(fft_size, dtype=np.float64)
        x_first[:w] = x[:w]
        x_full = np.zeros(fft_size, dtype=np.float64)
        x_full[:n] = x

        acf = np.fft.irfft(
            np.conj(np.fft.rfft(x_first)) * np.fft.rfft(x_full)
        )[: tau_max + 1]

        sq = x * x
        csum = np.concatenate(([0.0], np.cumsum(sq)))
        e0 = csum[w]
        e_tau = csum[w : w + tau_max + 1] - csum[0 : tau_max + 1]

        d = e0 + e_tau - 2.0 * acf
        d[0] = 0.0

        # Función de Diferencia Normalizada Acumulada (CMNDF)
        cmndf = np.ones_like(d)
        running_sum = np.cumsum(d[1:])
        taus = np.arange(1, len(d), dtype=np.float64)
        cmndf[1:] = np.where(running_sum > 1e-12, d[1:] * taus / running_sum, 1.0)

        # Búsqueda del primer mínimo local por debajo del umbral absoluto
        tau_best = -1
        tau = tau_min
        while tau < tau_max - 1:
            if cmndf[tau] < self.threshold:
                while tau + 1 < tau_max and cmndf[tau + 1] < cmndf[tau]:
                    tau += 1
                tau_best = tau
                break
            tau += 1

        if tau_best == -1:
            sub = cmndf[tau_min:tau_max]
            rel_idx = int(np.argmin(sub))
            if sub[rel_idx] < 0.40:
                tau_best = tau_min + rel_idx
            else:
                return PitchResult(0.0, 0.0, rms, now)

        # Interpolación parabólica sub-muestra
        if 1 <= tau_best < len(cmndf) - 1:
            alpha = float(cmndf[tau_best - 1])
            beta = float(cmndf[tau_best])
            gamma = float(cmndf[tau_best + 1])
            denom = alpha - 2.0 * beta + gamma
            if abs(denom) > 1e-12:
                delta = max(-0.5, min(0.5, 0.5 * (alpha - gamma) / denom))
            else:
                delta = 0.0
            tau_refined = tau_best + delta
            val_refined = beta - 0.25 * (alpha - gamma) * delta
        else:
            tau_refined = float(tau_best)
            val_refined = float(cmndf[tau_best])

        freq_hz = float(self.sample_rate / tau_refined)
        confidence = max(0.0, min(1.0, 1.0 - val_refined))
        return PitchResult(freq_hz=freq_hz, confidence=confidence, rms=rms, timestamp=now)


class PitchStabilizer:
    """
    Filtro de mediana temporal para suprimir transitorios de ataque
    (punteo del plectro en clavecín o arranque de aire en tubos de órgano).
    """

    def __init__(self, window_size: int = 3, min_confidence: float = 0.65) -> None:
        self.window_size = max(1, window_size)
        self.min_confidence = min_confidence
        self._history: deque[float] = deque(maxlen=self.window_size)

    def reset(self) -> None:
        self._history.clear()

    def update(self, reading: PitchResult) -> PitchResult:
        if reading.freq_hz <= 0.0 or reading.confidence < self.min_confidence:
            if len(self._history) > 0:
                self._history.popleft()
            if not self._history:
                return PitchResult(0.0, 0.0, reading.rms, reading.timestamp)

        if reading.freq_hz > 0.0 and reading.confidence >= self.min_confidence:
            self._history.append(reading.freq_hz)

        if not self._history:
            return PitchResult(0.0, 0.0, reading.rms, reading.timestamp)

        median_freq = float(statistics.median(self._history))
        return PitchResult(
            freq_hz=median_freq,
            confidence=reading.confidence,
            rms=reading.rms,
            timestamp=reading.timestamp,
        )
