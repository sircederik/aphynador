from __future__ import annotations

from enum import Enum


class Tier(str, Enum):
    FREE = "free"
    PRO = "pro"


class Feature(str, Enum):
    BASIC_TUNER = "basic_tuner"
    CUSTOM_TEMPERAMENTS = "custom_temperaments"
    SCALA_IMPORT_EXPORT = "scala_import_export"
    MANUAL_MODE_EXTENDED = "manual_mode_extended"
    BEAT_AND_COMMA_METRICS = "beat_and_comma_metrics"
    WAVEFORM_SELECTOR = "waveform_selector"
    UNLIMITED_LOGBOOK = "unlimited_logbook"
    CLIMATE_ANALYTICS = "climate_analytics"
    PARTITION_ASSISTANT = "partition_assistant"
    MATCH_PITCH_CALIBRATION = "match_pitch_calibration"
    INHARMONICITY_COMPENSATION = "inharmonicity_compensation"


FREE_FEATURES: frozenset[Feature] = frozenset({Feature.BASIC_TUNER})
FREE_BASIC_TEMPERAMENTS: frozenset[str] = frozenset(
    {
        "equal_temperament",
        "meantone_quarter_comma",
        "werckmeister_iii",
        "vallotti",
    }
)


class EntitlementManager:
    def __init__(self, tier: Tier = Tier.FREE) -> None:
        self.tier = tier

    def is_pro(self) -> bool:
        return self.tier == Tier.PRO

    def can_use(self, feature: Feature) -> bool:
        if self.tier == Tier.PRO:
            return True
        return feature in FREE_FEATURES

    def can_use_temperament(self, temperament_id: str) -> bool:
        if self.tier == Tier.PRO:
            return True
        return temperament_id in FREE_BASIC_TEMPERAMENTS

    def max_logbook_sessions(self) -> int | None:
        return None if self.tier == Tier.PRO else 3
