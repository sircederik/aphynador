from __future__ import annotations

from pathlib import Path
import flet as ft

from core.acoustics import NOTE_NAMES_SHARP
from core.entitlements import EntitlementManager, Feature
from core.i18n import LocalizationManager
from core.key_analysis import analyze_temperament_keys
from core.temperaments import (
    Temperament,
    TemperamentLibrary,
    export_scala_scl,
    import_scala_scl,
)
from ui.compat import make_button


class LibraryEditorView(ft.Column):
    def __init__(
        self,
        library: TemperamentLibrary,
        i18n: LocalizationManager,
        entitlements: EntitlementManager,
        active_temperament: Temperament,
        on_library_updated,
        on_notify,
    ) -> None:
        super().__init__(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        self.library = library
        self.i18n = i18n
        self.entitlements = entitlements
        self.active_temperament = active_temperament
        self.on_library_updated = on_library_updated
        self.on_notify = on_notify

        self.txt_didactic_header = ft.Text("", size=20, weight=ft.FontWeight.BOLD)
        self.txt_history = ft.Text("", size=13)
        self.txt_pros = ft.Text("", size=13)
        self.txt_contras = ft.Text("", size=13)
        self.txt_repertoire = ft.Text("", size=13)
        self.key_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Tonalidad")),
                ft.DataColumn(ft.Text("3.ª Mayor (c)")),
                ft.DataColumn(ft.Text("Desv. 5/4")),
                ft.DataColumn(ft.Text("Quinta (c)")),
                ft.DataColumn(ft.Text("Carácter")),
            ],
            rows=[],
        )

        self.tf_new_name = ft.TextField(label="Nombre del temperamento", value="Mi Temperamento", width=260)
        self.offset_fields: list[ft.TextField] = [
            ft.TextField(
                label=NOTE_NAMES_SHARP[i],
                value=str(self.active_temperament.offsets_cents[i]),
                width=78,
            )
            for i in range(12)
        ]
        self.tf_scl_path = ft.TextField(
            label="Ruta archivo .scl (importar / exportar)",
            value="data/temperaments/custom.scl",
            width=320,
        )

        self.controls = [
            ft.Text(self.i18n.t("library.didactics"), size=18, weight=ft.FontWeight.BOLD),
            self.txt_didactic_header,
            self.txt_history,
            self.txt_pros,
            self.txt_contras,
            self.txt_repertoire,
            ft.Divider(),
            ft.Text(self.i18n.t("library.key_map"), size=16, weight=ft.FontWeight.BOLD),
            self.key_table,
            ft.Divider(),
            ft.Text(self.i18n.t("editor.title"), size=18, weight=ft.FontWeight.BOLD),
            ft.Row(wrap=True, controls=[self.tf_new_name]),
            ft.Row(wrap=True, spacing=8, controls=self.offset_fields),
            ft.Row(
                wrap=True,
                controls=[
                    make_button(self.i18n.t("editor.save_json"), self._on_save_custom),
                    self.tf_scl_path,
                    ft.OutlinedButton(self.i18n.t("editor.import_scl"), on_click=self._on_import_scl),
                    ft.OutlinedButton(self.i18n.t("editor.export_scl"), on_click=self._on_export_scl),
                ],
            ),
        ]
        self.load_temperament(active_temperament)

    def load_temperament(self, temperament: Temperament) -> None:
        self.active_temperament = temperament
        lang = self.i18n.current_lang
        info = temperament.get_didactics(lang)
        self.txt_didactic_header.value = f"{info.get('name', temperament.id)} — {info.get('author_year', '')}"
        self.txt_history.value = f"• {self.i18n.t('library.history')}: {info.get('history', '')}"
        self.txt_pros.value = f"• {self.i18n.t('library.pros')}: {info.get('pros', '')}"
        self.txt_contras.value = f"• {self.i18n.t('library.contras')}: {info.get('contras', '')}"
        self.txt_repertoire.value = f"• {self.i18n.t('library.repertoire')}: {info.get('repertoire', '')}"

        for i, val in enumerate(temperament.offsets_cents):
            self.offset_fields[i].value = f"{val:.2f}"

        rows: list[ft.DataRow] = []
        for k in analyze_temperament_keys(temperament.offsets_cents):
            if k.is_wolf_fifth:
                tag = "Quinta del Lobo"
            elif k.is_pure_third:
                tag = "3.ª Pura (5/4)"
            else:
                tag = "Temperada"
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"{k.key_name} Mayor")),
                        ft.DataCell(ft.Text(f"{k.major_third_cents:.2f}")),
                        ft.DataCell(ft.Text(f"{k.major_third_err_from_pure:+.2f} c")),
                        ft.DataCell(ft.Text(f"{k.fifth_cents:.2f}")),
                        ft.DataCell(ft.Text(tag)),
                    ]
                )
            )
        self.key_table.rows = rows

    def _on_save_custom(self, _e) -> None:
        if not self.entitlements.can_use(Feature.CUSTOM_TEMPERAMENTS):
            self.on_notify(self.i18n.t("pro.badge"))
            return
        try:
            offsets = [float(tf.value) for tf in self.offset_fields]
            name = self.tf_new_name.value.strip() or "Custom"
            t_id = name.lower().replace(" ", "_")
            custom = Temperament(
                id=t_id,
                category="custom",
                offsets_cents=offsets,
                didactics={
                    "es": {"name": name, "author_year": "Personalizado", "history": "Creado en el editor."},
                    "en": {"name": name, "author_year": "Custom", "history": "Created in editor."},
                },
            )
            saved = self.library.save_custom(custom)
            self.on_library_updated()
            self.on_notify(f"Temperamento guardado en {saved}")
        except Exception as exc:
            self.on_notify(f"Error al guardar: {exc}")

    def _on_import_scl(self, _e) -> None:
        if not self.entitlements.can_use(Feature.SCALA_IMPORT_EXPORT):
            self.on_notify(self.i18n.t("pro.badge"))
            return
        try:
            imported = import_scala_scl(Path(self.tf_scl_path.value.strip()))
            self.library.save_custom(imported)
            self.load_temperament(imported)
            self.on_library_updated()
            self.on_notify(f"Scala importado: {imported.id}")
        except Exception as exc:
            self.on_notify(f"Error importando .scl: {exc}")

    def _on_export_scl(self, _e) -> None:
        if not self.entitlements.can_use(Feature.SCALA_IMPORT_EXPORT):
            self.on_notify(self.i18n.t("pro.badge"))
            return
        try:
            out = export_scala_scl(
                self.active_temperament,
                Path(self.tf_scl_path.value.strip()),
                lang=self.i18n.current_lang,
            )
            self.on_notify(f"Exportado a {out}")
        except Exception as exc:
            self.on_notify(f"Error exportando .scl: {exc}")
