from __future__ import annotations

import json
from pathlib import Path
import shutil


class LocalizationManager:
    def __init__(self, locales_dir: str | Path, default_lang: str = "es") -> None:
        self.locales_dir = Path(locales_dir)
        self.locales_dir.mkdir(parents=True, exist_ok=True)
        self.default_lang = default_lang
        self.current_lang = default_lang
        self._translations: dict[str, dict[str, str]] = {}
        self.reload()

    def reload(self) -> None:
        self._translations.clear()
        for file_path in sorted(self.locales_dir.glob("*.json")):
            with file_path.open("r", encoding="utf-8") as fh:
                self._translations[file_path.stem] = json.load(fh)

    def available_languages(self) -> list[str]:
        return sorted(self._translations.keys())

    def set_language(self, lang: str) -> None:
        if lang not in self._translations:
            raise KeyError(f"Idioma no disponible: {lang}")
        self.current_lang = lang

    def import_translation_file(self, external_json_path: str | Path) -> str:
        src = Path(external_json_path)
        with src.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("El archivo de traducción debe contener un objeto JSON plano.")
        lang_code = src.stem.lower()
        dest = self.locales_dir / f"{lang_code}.json"
        shutil.copy2(src, dest)
        self._translations[lang_code] = {str(k): str(v) for k, v in data.items()}
        return lang_code

    def t(self, key: str, **kwargs: object) -> str:
        lang_map = self._translations.get(self.current_lang, {})
        fallback_map = self._translations.get(self.default_lang, {})
        template = lang_map.get(key) or fallback_map.get(key) or key
        if kwargs:
            return template.format(**kwargs)
        return template
