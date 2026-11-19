from __future__ import annotations

from dataclasses import dataclass
import time
import numpy as np

from audio.detector import PitchResult, PitchStabilizer, YinPitchDetector
from audio.synthesizer import ReferenceSynthesizer, Waveform


@dataclass(frozen=True)
class EngineSnapshot:
    pitch: PitchResult
    synth_enabled: bool
    synth_freq_hz: float
    synth_waveform: Waveform


class DuplexAudioEngine:
    """
    Motor de audio bidireccional desacoplado de la interfaz gráfica.
    Procesa entrada de micrófono y salida de referencia en tiempo real,
    publicando instantáneas atómicas sin bloqueos para la UI.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        block_size: int = 4096,
        detector: YinPitchDetector | None = None,
        stabilizer: PitchStabilizer | None = None,
        synthesizer: ReferenceSynthesizer | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.detector = detector or YinPitchDetector(sample_rate=sample_rate)
        self.stabilizer = stabilizer or PitchStabilizer(window_size=3)
        self.synthesizer = synthesizer or ReferenceSynthesizer(sample_rate=sample_rate)

        self._snapshot = EngineSnapshot(
            pitch=PitchResult(0.0, 0.0, 0.0, time.monotonic()),
            synth_enabled=False,
            synth_freq_hz=415.0,
            synth_waveform=Waveform.SINE,
        )
        self._stream = None

    def get_snapshot(self) -> EngineSnapshot:
        """Lectura atómica instantánea para la interfaz gráfica (30-60 FPS)."""
        return self._snapshot

    def process_block(
        self,
        indata: np.ndarray | None,
        num_frames: int,
        timestamp: float | None = None,
    ) -> np.ndarray:
        """
        Ejecuta un ciclo completo de análisis + síntesis.
        Puede ser invocado por sounddevice o por puentes nativos Android/iOS.
        """
        now = time.monotonic() if timestamp is None else timestamp

        if indata is not None and len(indata) > 0:
            raw_pitch = self.detector.detect(indata, timestamp=now)
            stable_pitch = self.stabilizer.update(raw_pitch)
        else:
            stable_pitch = PitchResult(0.0, 0.0, 0.0, now)

        out_block = self.synthesizer.render_block(num_frames)

        # Publicación atómica por reasignación de referencia (thread-safe en Python)
        self._snapshot = EngineSnapshot(
            pitch=stable_pitch,
            synth_enabled=self.synthesizer.is_enabled,
            synth_freq_hz=self.synthesizer.frequency,
            synth_waveform=self.synthesizer.waveform,
        )
        return out_block

    def _sd_callback(self, indata, outdata, frames, time_info, status) -> None:
        out_mono = self.process_block(indata, frames)
        outdata[:, 0] = out_mono
        if outdata.shape[1] > 1:
            outdata[:, 1:] = out_mono[:, None]

    def start(self, device: int | str | tuple[int, int] | None = None) -> None:
        if self._stream is not None:
            return
        import sounddevice as sd

        self._stream = sd.Stream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            device=device,
            channels=(1, 1),
            dtype="float32",
            callback=self._sd_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.stabilizer.reset()
