from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Sequence

from core.acoustics import (
    PURE_FIFTH_CENTS,
    PYTHAGOREAN_COMMA_CENTS,
    SYNTONIC_COMMA_CENTS,
)

# Orden ascendente de quintas partiendo de C (0): C-G-D-A-E-B-F#-C#-G#-Eb-Bb-F
CIRCLE_OF_FIFTHS_UP: tuple[int, ...] = (0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5)


@dataclass
class Temperament:
    id: str
    category: str
    offsets_cents: list[float]
    didactics: dict[str, dict[str, str]] = field(default_factory=dict)
    partition_sequence: list[dict[str, Any]] = field(default_factory=list)
    version: str = "1.0"

    def __post_init__(self) -> None:
        validate_offsets(self.offsets_cents)
        self.offsets_cents = [round(float(x), 4) for x in self.offsets_cents]

    def get_didactics(self, lang: str = "es") -> dict[str, str]:
        if lang in self.didactics:
            return self.didactics[lang]
        if "es" in self.didactics:
            return self.didactics["es"]
        if "en" in self.didactics:
            return self.didactics["en"]
        return {
            "name": self.id,
            "author_year": "",
            "history": "",
            "pros": "",
            "contras": "",
            "repertoire": "",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "category": self.category,
            "offsets_cents": self.offsets_cents,
            "didactics": self.didactics,
            "partition_sequence": self.partition_sequence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Temperament:
        return cls(
            id=str(data["id"]),
            version=str(data.get("version", "1.0")),
            category=str(data.get("category", "custom")),
            offsets_cents=list(data["offsets_cents"]),
            didactics=dict(data.get("didactics", {})),
            partition_sequence=list(data.get("partition_sequence", [])),
        )


def validate_offsets(offsets: Sequence[float]) -> None:
    if len(offsets) != 12:
        raise ValueError("Un temperamento cromático debe tener exactamente 12 notas.")
    for val in offsets:
        if not (-100.0 <= float(val) <= 100.0):
            raise ValueError(f"Desviación fuera de rango razonable (-100..+100 c): {val}")


def build_offsets_from_fifths(
    up_fifths_tempering: Sequence[tuple[str, float]],
    down_fifths_tempering: Sequence[tuple[str, float]],
) -> list[float]:
    """
    Construye los 12 offsets respecto a ET partiendo de C = 0.0 cents:
    - up_fifths_tempering: lista de tuplas (tipo_coma, fraccion) hacia arriba
      (C-G, G-D, D-A, A-E, E-B, B-F#, F#-C#, C#-G#). Ej: ("pythagorean", -0.25)
    - down_fifths_tempering: lista de tuplas hacia abajo (C-F, F-Bb, Bb-Eb).
    """
    def resolve_fifth_cents(comma_type: str, fraction: float) -> float:
        if comma_type == "pythagorean":
            comma = PYTHAGOREAN_COMMA_CENTS
        elif comma_type == "syntonic":
            comma = SYNTONIC_COMMA_CENTS
        else:
            comma = 0.0
        return PURE_FIFTH_CENTS + (fraction * comma)

    offsets = [0.0] * 12

    # Cadena ascendente desde C
    acc_up = 0.0
    for idx, (c_type, frac) in enumerate(up_fifths_tempering):
        pitch_class = CIRCLE_OF_FIFTHS_UP[idx + 1]
        acc_up += resolve_fifth_cents(c_type, frac) - 700.0
        offsets[pitch_class] = round(acc_up, 2)

    # Cadena descendente desde C (C -> F -> Bb -> Eb)
    down_pcs = (5, 10, 3)
    acc_down = 0.0
    for idx, (c_type, frac) in enumerate(down_fifths_tempering):
        pitch_class = down_pcs[idx]
        acc_down -= resolve_fifth_cents(c_type, frac) - 700.0
        offsets[pitch_class] = round(acc_down, 2)

    return offsets


def load_temperament_json(path: str | Path) -> Temperament:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return Temperament.from_dict(data)


def save_temperament_json(temperament: Temperament, path: str | Path) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as fh:
        json.dump(temperament.to_dict(), fh, indent=2, ensure_ascii=False)
    return file_path


def import_scala_scl(path: str | Path, temperament_id: str | None = None) -> Temperament:
    """
    Importa un archivo de afinación en formato estándar Scala (.scl) de 12 notas
    (soporta tanto valores en cents con punto decimal como razones enteras '3/2').
    """
    file_path = Path(path)
    raw_text = file_path.read_text(encoding="utf-8")
    clean_lines: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.split("!")[0].strip()
        if stripped:
            clean_lines.append(stripped)

    if len(clean_lines) < 14:
        raise ValueError("El archivo Scala (.scl) no contiene suficientes líneas válidas.")

    description = clean_lines[0]
    note_count = int(clean_lines[1])
    if note_count != 12:
        raise ValueError(f"Solo se soportan escalas de 12 notas (recibido: {note_count}).")

    degrees_cents = [0.0]
    for entry in clean_lines[2:14]:
        token = entry.split()[0]
        if "." in token:
            val = float(token)
        elif "/" in token:
            num_s, den_s = token.split("/", 1)
            val = 1200.0 * math.log2(float(num_s) / float(den_s))
        else:
            val = 1200.0 * math.log2(float(token))
        degrees_cents.append(val)

    offsets = [round(degrees_cents[i] - (i * 100.0), 4) for i in range(12)]
    t_id = temperament_id or file_path.stem.lower().replace(" ", "_")

    return Temperament(
        id=t_id,
        category="imported_scala",
        offsets_cents=offsets,
        didactics={
            "es": {
                "name": description,
                "author_year": "Importado desde Scala (.scl)",
                "history": f"Escala importada desde el archivo {file_path.name}.",
                "pros": "",
                "contras": "",
                "repertoire": "",
            },
            "en": {
                "name": description,
                "author_year": "Imported from Scala (.scl)",
                "history": f"Scale imported from file {file_path.name}.",
                "pros": "",
                "contras": "",
                "repertoire": "",
            },
        },
    )


def export_scala_scl(temperament: Temperament, path: str | Path, lang: str = "es") -> Path:
    """Exporta un temperamento al formato estándar Scala (.scl)."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    info = temperament.get_didactics(lang)
    lines = [
        f"! {file_path.name}",
        f"! Exportado por Aphynador ({temperament.id})",
        info.get("name", temperament.id),
        " 12",
        "!",
    ]
    # Grados 1..11 (C#..B) más la octava 2/1
    for i in range(1, 12):
        cents_val = (i * 100.0) + temperament.offsets_cents[i]
        lines.append(f" {cents_val:.5f}")
    lines.append(" 2/1")

    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return file_path


class TemperamentLibrary:
    """Gestor de colección de temperamentos (1 archivo JSON por temperamento)."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, Temperament] = {}
        self.reload()

    def reload(self) -> None:
        self._items.clear()
        for json_file in sorted(self.directory.glob("*.json")):
            temp = load_temperament_json(json_file)
            self._items[temp.id] = temp

    def list_all(self) -> list[Temperament]:
        return list(self._items.values())

    def get(self, temperament_id: str) -> Temperament:
        if temperament_id not in self._items:
            raise KeyError(f"Temperamento no encontrado: {temperament_id}")
        return self._items[temperament_id]

    def save_custom(self, temperament: Temperament) -> Path:
        target = self.directory / f"{temperament.id}.json"
        save_temperament_json(temperament, target)
        self._items[temperament.id] = temperament
        return target
