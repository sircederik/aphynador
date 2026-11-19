from __future__ import annotations

import asyncio
from pathlib import Path
import time
import flet as ft

from audio.engine import DuplexAudioEngine
from core.entitlements import EntitlementManager, Tier
from core.i18n import LocalizationManager
from core.temperaments import TemperamentLibrary
from ui.compat import make_button, set_button_label
from ui.theme import ThemeChoice, resolve_palette, to_flet_theme_mode
from ui.views.library_editor_view import LibraryEditorView
from ui.views.settings_view import SettingsView
from ui.views.tuner_view import TunerView


async def main(page: ft.Page) -> None:
    base_dir = Path(__file__).resolve().parent
    library = TemperamentLibrary(base_dir / "data" / "temperaments")
    i18n = LocalizationManager(base_dir / "data" / "locales", default_lang="es")
    entitlements = EntitlementManager(tier=Tier.PRO)
    engine = DuplexAudioEngine(sample_rate=44100, block_size=4096)

    theme_choice = ThemeChoice.DARK
    palette = resolve_palette(theme_choice, page.platform_brightness)

    page.title = i18n.t("app.title")
    page.theme_mode = to_flet_theme_mode(theme_choice)
    page.bgcolor = palette.bg_primary
    page.padding = 16

    active_tab = 0

    def notify(message: str) -> None:
        snack = ft.SnackBar(content=ft.Text(message))
        if hasattr(page, "show_dialog"):
            page.show_dialog(snack)
        else:
            page.overlay.append(snack)
            snack.open = True
        page.update()

    def on_temperament_changed(temp) -> None:
        library_view.load_temperament(temp)
        page.update()

    def on_library_updated() -> None:
        tuner_view.refresh_translations()
        page.update()

    def on_theme_changed(choice: ThemeChoice) -> None:
        nonlocal theme_choice, palette
        theme_choice = choice
        palette = resolve_palette(choice, page.platform_brightness)
        page.theme_mode = to_flet_theme_mode(choice)
        page.bgcolor = palette.bg_primary
        tuner_view.apply_palette(palette)
        page.update()

    def on_language_changed(lang: str) -> None:
        i18n.set_language(lang)
        page.title = i18n.t("app.title")
        tuner_view.refresh_translations()
        library_view.load_temperament(tuner_view.active_temperament)
        set_button_label(btn_tab_tuner, i18n.t("tab.tuner"))
        set_button_label(btn_tab_library, i18n.t("tab.library"))
        set_button_label(btn_tab_settings, i18n.t("tab.settings"))
        page.update()

    def on_tier_changed(new_tier: Tier) -> None:
        entitlements.tier = new_tier
        tuner_view.refresh_translations()
        page.update()

    tuner_view = TunerView(
        engine=engine,
        library=library,
        i18n=i18n,
        entitlements=entitlements,
        palette=palette,
        on_temperament_changed=on_temperament_changed,
        on_notify=notify,
    )
    library_view = LibraryEditorView(
        library=library,
        i18n=i18n,
        entitlements=entitlements,
        active_temperament=tuner_view.active_temperament,
        on_library_updated=on_library_updated,
        on_notify=notify,
    )
    settings_view = SettingsView(
        i18n=i18n,
        entitlements=entitlements,
        on_theme_changed=on_theme_changed,
        on_language_changed=on_language_changed,
        on_tier_changed=on_tier_changed,
        on_notify=notify,
    )

    views = [tuner_view, library_view, settings_view]
    body_container = ft.Container(content=tuner_view, expand=True)

    def switch_tab(idx: int) -> None:
        nonlocal active_tab
        active_tab = idx
        body_container.content = views[idx]
        page.update()

    btn_tab_tuner = make_button(i18n.t("tab.tuner"), lambda _: switch_tab(0))
    btn_tab_library = make_button(i18n.t("tab.library"), lambda _: switch_tab(1))
    btn_tab_settings = make_button(i18n.t("tab.settings"), lambda _: switch_tab(2))

    nav_bar = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=12,
        controls=[btn_tab_tuner, btn_tab_library, btn_tab_settings],
    )

    page.add(ft.Column(expand=True, controls=[nav_bar, ft.Divider(height=1), body_container]))

    running = True
    try:
        engine.start()
    except Exception as exc:
        notify(f"Aviso de dispositivo de audio: {exc}")

    def on_disconnect(_e) -> None:
        nonlocal running
        running = False
        engine.stop()

    page.on_disconnect = on_disconnect

    async def refresh_loop() -> None:
        last_t = time.monotonic()
        while running:
            now = time.monotonic()
            dt = now - last_t
            last_t = now
            if active_tab == 0:
                tuner_view.update_frame(dt)
                page.update()
            await asyncio.sleep(1.0 / 30.0)

    page.run_task(refresh_loop)


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
