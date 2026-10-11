import json
from pathlib import Path
from threading import Lock

from config import DATA_DIR
FILE_PATH = DATA_DIR / "regulation_parameters.json"

DEFAULTS = {
    "sprint_impact_weight": 0.10,
    "wet_race_uncertainty": 0.10,
    "reliability_weight": 0.20,
    "budget_cap_upgrade_weight": 0.10,
    "aero_rule_change_weight": 0.10,
    "safety_car_randomness": 0.05,
}

ALLOWED_KEYS = set(DEFAULTS.keys())


class RegulationService:
    """CU-12: Regulation Impact Module (JSON-backed for simplicity)."""

    _lock = Lock()

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not FILE_PATH.exists():
            self._write(DEFAULTS)

    def _read(self):
        try:
            with FILE_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULTS)
            merged.update({k: v for k, v in data.items() if k in ALLOWED_KEYS})
            return merged
        except Exception:
            return dict(DEFAULTS)

    def _write(self, params):
        with FILE_PATH.open("w", encoding="utf-8") as f:
            json.dump(params, f, indent=2)

    def get(self):
        return self._read()

    def save(self, payload):
        with self._lock:
            current = self._read()
            for key, value in (payload or {}).items():
                if key in ALLOWED_KEYS:
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        continue
                    current[key] = max(0.0, min(1.0, value))
            self._write(current)
            return current

    def reset(self):
        with self._lock:
            self._write(DEFAULTS)
            return dict(DEFAULTS)

    def adjustment_factor(self):
        """Return a small multiplier in ~[0.85, 1.15] derived from regulations.

        Higher reliability => slight bonus.
        Higher uncertainty/randomness/rule changes => slight dampening.
        """
        p = self._read()
        bonus = p["reliability_weight"] * 0.10
        penalty = (
            p["wet_race_uncertainty"] * 0.05
            + p["aero_rule_change_weight"] * 0.05
            + p["safety_car_randomness"] * 0.05
            + p["sprint_impact_weight"] * 0.02
            - p["budget_cap_upgrade_weight"] * 0.03
        )
        return round(max(0.85, min(1.15, 1.0 + bonus - penalty)), 4)
