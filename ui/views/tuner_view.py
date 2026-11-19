from __future__ import annotations

import flet as ft

from audio.engine import DuplexAudioEngine
from audio.synthesizer import Waveform
from core.acoustics import (
    calculate_interval_beats,
    calibrate_a4_from_measured_note,
    detect_nearest_note_auto,
    evaluate_manual_note,
    midi_note_label,
    midi_to_target_freq,
)
from core.entitlements import EntitlementManager, Feature
from core.i18n import LocalizationManager
from core.partition import PartitionAssistant
from core.temperaments import Temperament, TemperamentLibrary
from ui.compat import border_all, make_button, make_dropdown, set_button_label
from ui.needle_gauge import AnalogNeedleGauge
from ui.theme import AppPalette


class TunerView(ft.Column):
    def __init__(
        self,
        engine: DuplexAudioEngine,
        library: TemperamentLibrary,
        i18n: LocalizationManager,
        entitlements: EntitlementManager,
        palette: AppPalette,
        on_temperament_changed,
        on_notify,
    ) -> None:
        super().__init__(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        self.engine = engine
        self.library = library
        self.i18n = i18n
        self.entitlements = entitlements
        self.palette = palette
        self.on_temperament_changed = on_temperament_changed
        self.on_notify = on_notify

        self.mode: str = "auto"
        self.manual_midi: int = 69
        self.a4_ref: float = 415.0
        self.inharmonicity_b: float = 0.0
        self.beat_ref_midi: int = 60
        self._last_measured_freq: float = 0.0

        all_temps = self.library.list_all()
        self.active_temperament: Temperament = (
            self.library.get("werckmeister_iii")
            if any(t.id == "werckmeister_iii" for t in all_temps)
            else all_temps[0]
        )
        self.partition = PartitionAssistant(self.active_temperament, a4_ref=self.a4_ref)

        self.gauge = AnalogNeedleGauge(width=460, height=225, palette=palette)

        self.btn_mode = make_button(self.i18n.t("mode.auto"), self._toggle_mode)
        self.btn_note_down = ft.IconButton(icon=ft.Icons.ARROW_LEFT, on_click=lambda _: self._step_manual_note(-1))
        self.lbl_manual_note = ft.Text("A4", size=16, weight=ft.FontWeight.BOLD)
        self.btn_note_up = ft.IconButton(icon=ft.Icons.ARROW_RIGHT, on_click=lambda _: self._step_manual_note(1))

        self.dd_temperament = make_dropdown(
            label=self.i18n.t("controls.temperament"),
            value=self.active_temperament.id,
            options=[],
            width=260,
            on_change=self._on_temp_select,
        )
        self.tf_a4 = ft.TextField(
            label=self.i18n.t("controls.a4_ref"),
            value="415.0",
            width=120,
            on_submit=self._on_a4_submit,
        )
        self.btn_match_pitch = ft.OutlinedButton(
            self.i18n.t("controls.match_pitch"),
            on_click=self._on_match_pitch,
        )
        self.slider_inharm = ft.Slider(
            min=0.0,
            max=0.0005,
            divisions=50,
            value=0.0,
            label="B = {value}",
            width=180,
            on_change=self._on_inharm_change,
        )

        self.lbl_big_note = ft.Text("--", size=54, weight=ft.FontWeight.BOLD)
        self.lbl_freqs = ft.Text("0.00 Hz  |  Target: 0.00 Hz", size=14)
        self.lbl_cents_val = ft.Text("0.0 c", size=22, weight=ft.FontWeight.BOLD)
        self.lbl_comma_val = ft.Text("0 CS", size=18, weight=ft.FontWeight.W_600)
        self.lbl_beats_val = ft.Text("0.00 bat/s", size=18, weight=ft.FontWeight.W_600)

        self.dd_beat_ref = make_dropdown(
            label=self.i18n.t("controls.ref_interval"),
            value="60",
            width=145,
            options=[
                ft.dropdown.Option(str(m), midi_note_label(m)[2])
                for m in range(48, 84)
            ],
            on_change=self._on_beat_ref_change,
        )

        self.sw_synth = ft.Switch(
            label=self.i18n.t("synth.enable"),
            value=False,
            on_change=self._on_synth_toggle,
        )
        self.dd_waveform = make_dropdown(
            label=self.i18n.t("synth.waveform"),
            value=Waveform.SINE.value,
            options=[],
            width=220,
            on_change=self._on_waveform_change,
        )
        self.slider_volume = ft.Slider(
            min=0.0,
            max=0.9,
            value=0.35,
            width=150,
            on_change=self._on_volume_change,
        )

        self.lbl_partition_step = ft.Text("", size=14, weight=ft.FontWeight.W_600)
        self.pb_partition = ft.ProgressBar(value=0.0, width=320)
        self.btn_partition_reset = ft.TextButton(
            self.i18n.t("partition.reset"),
            on_click=self._reset_partition,
        )

        self._rebuild_layout()
        self.refresh_translations()

    def _rebuild_layout(self) -> None:
        self.controls = [
            ft.Row(
                wrap=True,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    self.dd_temperament,
                    self.tf_a4,
                    self.btn_match_pitch,
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text(self.i18n.t("controls.inharmonicity"), size=11),
                            self.slider_inharm,
                        ],
                    ),
                ],
            ),
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    self.btn_mode,
                    self.btn_note_down,
                    self.lbl_manual_note,
                    self.btn_note_up,
                    self.dd_beat_ref,
                ],
            ),
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[self.gauge],
            ),
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[
                    self.lbl_big_note,
                    self.lbl_freqs,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=28,
                        controls=[
                            self.lbl_cents_val,
                            self.lbl_comma_val,
                            self.lbl_beats_val,
                        ],
                    ),
                ],
            ),
            ft.Container(
                padding=12,
                border_radius=10,
                border=border_all(1, self.palette.border_subtle),
                bgcolor=self.palette.bg_card,
                content=ft.Row(
                    wrap=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Text(self.i18n.t("synth.title"), weight=ft.FontWeight.BOLD),
                        self.sw_synth,
                        self.dd_waveform,
                        self.slider_volume,
                    ],
                ),
            ),
            ft.Container(
                padding=12,
                border_radius=10,
                border=border_all(1, self.palette.border_subtle),
                bgcolor=self.palette.bg_card,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                    controls=[
                        ft.Text(self.i18n.t("partition.title"), weight=ft.FontWeight.BOLD),
                        self.lbl_partition_step,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[self.pb_partition, self.btn_partition_reset],
                        ),
                    ],
                ),
            ),
        ]

    def refresh_translations(self) -> None:
        lang = self.i18n.current_lang
        self.dd_temperament.label = self.i18n.t("controls.temperament")
        self.dd_temperament.options = [
            ft.dropdown.Option(
                t.id,
                t.get_didactics(lang).get("name", t.id)
                + ("" if self.entitlements.can_use_temperament(t.id) else " [Pro]"),
            )
            for t in self.library.list_all()
        ]
        self.tf_a4.label = self.i18n.t("controls.a4_ref")
        set_button_label(self.btn_match_pitch, self.i18n.t("controls.match_pitch"))
        self.dd_beat_ref.label = self.i18n.t("controls.ref_interval")
        set_button_label(self.btn_mode, self.i18n.t("mode.auto" if self.mode == "auto" else "mode.manual"))
        self.sw_synth.label = self.i18n.t("synth.enable")
        self.dd_waveform.label = self.i18n.t("synth.waveform")
        self.dd_waveform.options = [
            ft.dropdown.Option(Waveform.SINE.value, self.i18n.t("wave.sine")),
            ft.dropdown.Option(Waveform.TRIANGLE.value, self.i18n.t("wave.triangle") + " [Pro]"),
            ft.dropdown.Option(Waveform.SAWTOOTH.value, self.i18n.t("wave.sawtooth") + " [Pro]"),
            ft.dropdown.Option(Waveform.ORGAN_PRINCIPAL.value, self.i18n.t("wave.organ_principal") + " [Pro]"),
            ft.dropdown.Option(Waveform.HARPSICHORD.value, self.i18n.t("wave.harpsichord") + " [Pro]"),
        ]
        set_button_label(self.btn_partition_reset, self.i18n.t("partition.reset"))
        self._update_partition_label()

    def apply_palette(self, palette: AppPalette) -> None:
        self.palette = palette
        self.gauge.apply_palette(palette)
        self._rebuild_layout()

    def _toggle_mode(self, _e) -> None:
        if self.mode == "auto" and not self.entitlements.can_use(Feature.MANUAL_MODE_EXTENDED):
            self.on_notify(self.i18n.t("pro.badge"))
            return
        self.mode = "manual" if self.mode == "auto" else "auto"
        self.gauge.set_mode(self.mode)
        set_button_label(self.btn_mode, self.i18n.t("mode.auto" if self.mode == "auto" else "mode.manual"))
        self._sync_synth_target_frequency()

    def _step_manual_note(self, delta: int) -> None:
        self.manual_midi = max(24, min(108, self.manual_midi + delta))
        _, _, label = midi_note_label(self.manual_midi)
        self.lbl_manual_note.value = label
        self._sync_synth_target_frequency()

    def _sync_synth_target_frequency(self) -> None:
        f_target = midi_to_target_freq(
            self.manual_midi,
            self.active_temperament.offsets_cents,
            self.a4_ref,
            self.inharmonicity_b,
        )
        self.engine.synthesizer.set_frequency(f_target)

    def _on_temp_select(self, e) -> None:
        chosen_id = e.control.value
        if not self.entitlements.can_use_temperament(chosen_id):
            self.on_notify(self.i18n.t("pro.badge"))
            e.control.value = self.active_temperament.id
            return
        self.active_temperament = self.library.get(chosen_id)
        self.partition = PartitionAssistant(
            self.active_temperament,
            a4_ref=self.a4_ref,
            inharmonicity_b=self.inharmonicity_b,
        )
        self._sync_synth_target_frequency()
        self._update_partition_label()
        self.on_temperament_changed(self.active_temperament)

    def _on_a4_submit(self, e) -> None:
        try:
            val = float(e.control.value)
            if 360.0 <= val <= 490.0:
                self.a4_ref = val
                self._sync_synth_target_frequency()
                self.partition = PartitionAssistant(
                    self.active_temperament, a4_ref=self.a4_ref, inharmonicity_b=self.inharmonicity_b
                )
                self._update_partition_label()
        except ValueError:
            pass

    def _on_match_pitch(self, _e) -> None:
        if not self.entitlements.can_use(Feature.MATCH_PITCH_CALIBRATION):
            self.on_notify(self.i18n.t("pro.badge"))
            return
        if self._last_measured_freq <= 0.0:
            self.on_notify("Toca una nota estable antes de capturar A4.")
            return
        new_a4 = calibrate_a4_from_measured_note(
            self._last_measured_freq,
            reference_midi=self.manual_midi,
            offsets_cents=self.active_temperament.offsets_cents,
            inharmonicity_b=self.inharmonicity_b,
        )
        self.a4_ref = round(new_a4, 2)
        self.tf_a4.value = f"{self.a4_ref:.2f}"
        self._sync_synth_target_frequency()
        self.on_notify(f"A4 calibrado a {self.a4_ref:.2f} Hz")

    def _on_inharm_change(self, e) -> None:
        if not self.entitlements.can_use(Feature.INHARMONICITY_COMPENSATION):
            e.control.value = 0.0
            self.on_notify(self.i18n.t("pro.badge"))
            return
        self.inharmonicity_b = float(e.control.value)
        self._sync_synth_target_frequency()

    def _on_beat_ref_change(self, e) -> None:
        self.beat_ref_midi = int(e.control.value)

    def _on_synth_toggle(self, e) -> None:
        self._sync_synth_target_frequency()
        self.engine.synthesizer.set_enabled(bool(e.control.value))

    def _on_waveform_change(self, e) -> None:
        wf = Waveform(e.control.value)
        if wf != Waveform.SINE and not self.entitlements.can_use(Feature.WAVEFORM_SELECTOR):
            e.control.value = Waveform.SINE.value
            self.on_notify(self.i18n.t("pro.badge"))
            return
        self.engine.synthesizer.set_waveform(wf)

    def _on_volume_change(self, e) -> None:
        self.engine.synthesizer.set_volume(float(e.control.value))

    def _reset_partition(self, _e) -> None:
        self.partition = PartitionAssistant(
            self.active_temperament, a4_ref=self.a4_ref, inharmonicity_b=self.inharmonicity_b
        )
        self.pb_partition.value = 0.0
        self._update_partition_label()

    def _update_partition_label(self) -> None:
        step = self.partition.current_step
        if step is None:
            self.lbl_partition_step.value = self.i18n.t("partition.completed")
            return
        desc = step.note_es if self.i18n.current_lang == "es" else step.note_en
        self.lbl_partition_step.value = (
            f"Paso {step.step_number}/{len(self.partition.steps)}: "
            f"{step.target_note_label} ({step.target_freq_hz:.2f} Hz) — {desc}"
        )

    def update_frame(self, dt: float) -> None:
        snap = self.engine.get_snapshot()
        freq = snap.pitch.freq_hz
        self._last_measured_freq = freq

        if freq <= 0.0:
            self.gauge.tick_physics(None, dt)
            return

        if self.mode == "auto":
            reading = detect_nearest_note_auto(
                freq,
                self.active_temperament.offsets_cents,
                a4_ref=self.a4_ref,
                inharmonicity_b=self.inharmonicity_b,
            )
            self.manual_midi = reading.midi_note
            self.lbl_manual_note.value = reading.full_name
        else:
            reading = evaluate_manual_note(
                freq,
                self.manual_midi,
                self.active_temperament.offsets_cents,
                a4_ref=self.a4_ref,
                inharmonicity_b=self.inharmonicity_b,
            )

        self.gauge.tick_physics(reading.cents_diff, dt)
        self.lbl_big_note.value = reading.full_name
        self.lbl_freqs.value = (
            f"{self.i18n.t('metrics.measured')}: {reading.measured_freq:.2f} Hz   |   "
            f"{self.i18n.t('metrics.target')}: {reading.target_freq:.2f} Hz"
        )
        sign = "+" if reading.cents_diff >= 0 else ""
        self.lbl_cents_val.value = f"{sign}{reading.cents_diff:.1f} c"

        if self.entitlements.can_use(Feature.BEAT_AND_COMMA_METRICS):
            self.lbl_comma_val.value = reading.comma_label
            low, high = min(reading.midi_note, self.beat_ref_midi), max(reading.midi_note, self.beat_ref_midi)
            try:
                b_res = calculate_interval_beats(
                    low, high, self.active_temperament.offsets_cents, self.a4_ref, self.inharmonicity_b
                )
                self.lbl_beats_val.value = f"{b_res.abs_beats_hz:.2f} bat/s ({b_res.character})"
            except ValueError:
                self.lbl_beats_val.value = "-- bat/s"
        else:
            self.lbl_comma_val.value = "Coma [Pro]"
            self.lbl_beats_val.value = "Batimentos [Pro]"

        if self.entitlements.can_use(Feature.PARTITION_ASSISTANT):
            step = self.partition.current_step
            if step is not None and reading.midi_note == step.target_midi:
                advanced = self.partition.update(reading.cents_diff, dt)
                self.pb_partition.value = self.partition.stability_progress
                if advanced:
                    self._update_partition_label()
