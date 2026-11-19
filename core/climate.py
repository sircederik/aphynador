from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class ClimateReading:
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float | None = None
    source: str = "manual"
    timestamp_iso: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp_iso:
            object.__setattr__(
                self, "timestamp_iso", datetime.now(timezone.utc).isoformat()
            )


class ClimateProvider(Protocol):
    def get_current_reading(self) -> ClimateReading:
        ...


class ManualClimateProvider:
    def __init__(
        self,
        temperature_c: float = 20.0,
        humidity_pct: float = 50.0,
        pressure_hpa: float | None = None,
    ) -> None:
        self._reading = ClimateReading(
            temperature_c=temperature_c,
            humidity_pct=humidity_pct,
            pressure_hpa=pressure_hpa,
            source="manual",
        )

    def update_values(
        self,
        temperature_c: float,
        humidity_pct: float,
        pressure_hpa: float | None = None,
    ) -> ClimateReading:
        self._reading = ClimateReading(
            temperature_c=temperature_c,
            humidity_pct=humidity_pct,
            pressure_hpa=pressure_hpa,
            source="manual",
        )
        return self._reading

    def get_current_reading(self) -> ClimateReading:
        return self._reading
