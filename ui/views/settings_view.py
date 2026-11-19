from __future__ import annotations

import flet as ft

from core.entitlements import EntitlementManager, Tier
from core.i18n import LocalizationManager
from ui.compat import make_dropdown
from ui.theme import ThemeChoice


class SettingsView(ft.Column):
    def __init__(
        self,
        i18n: LocalizationManager,
        entitlements: EntitlementManager,
        on_theme_changed,
        on_language_changed,
        on_tier_changed,
        on_notify,
    ) -> None:
        super().__init__(spacing=16, expand=True)
        self.i18n = i18n
        self.entitlements = entitlements
        self.on_theme_changed = on_theme_changed
        self.on_language_changed = on_language_changed
        self.on_tier_changed = on_tier_changed
        self.on_notify = on_notify

        self.dd_theme = make_dropdown(
            label=self.i18n.t("settings.theme"),
            value=ThemeChoice.DARK.value,
            width=240,
            options=[
                ft.dropdown.Option(ThemeChoice.SYSTEM.value, self.i18n.t("theme.system")),
                ft.dropdown.Option(ThemeChoice.LIGHT.value, self.i18n.t("theme.light")),
                ft.dropdown.Option(ThemeChoice.DARK.value, self.i18n.t("theme.dark")),
            ],
            on_change=lambda e: self.on_theme_changed(ThemeChoice(e.control.value)),
        )

        self.dd_lang = make_dropdown(
            label=self.i18n.t("settings.language"),
            value=self.i18n.current_lang,
            width=240,
            options=[ft.dropdown.Option(code, code.upper()) for code in self.i18n.available_languages()],
            on_change=lambda e: self.on_language_changed(e.control.value),
        )

        self.tf_import_lang = ft.TextField(
            label="Ruta archivo traducción (.json)",
            value="data/locales/de.json",
            width=280,
        )

        self.dd_tier = make_dropdown(
            label=self.i18n.t("settings.tier"),
            value=self.entitlements.tier.value,
            width=240,
            options=[
                ft.dropdown.Option(Tier.FREE.value, "Gratuita (Free)"),
                ft.dropdown.Option(Tier.PRO.value, "Completa (Pro)"),
            ],
            on_change=lambda e: self.on_tier_changed(Tier(e.control.value)),
        )

        self.controls = [
            self.dd_theme,
            ft.Row(
                wrap=True,
                controls=[
                    self.dd_lang,
                    self.tf_import_lang,
                    ft.OutlinedButton(
                        self.i18n.t("settings.import_lang"),
                        on_click=self._on_import_lang,
                    ),
                ],
            ),
            self.dd_tier,
        ]

    def _on_import_lang(self, _e) -> None:
        try:
            code = self.i18n.import_translation_file(self.tf_import_lang.value.strip())
            self.dd_lang.options = [
                ft.dropdown.Option(c, c.upper()) for c in self.i18n.available_languages()
            ]
            self.dd_lang.value = code
            self.on_language_changed(code)
            self.on_notify(f"Idioma '{code}' importado correctamente.")
        except Exception as exc:
            self.on_notify(f"Error importando idioma: {exc}")
