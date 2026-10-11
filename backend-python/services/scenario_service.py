import json
import uuid
from pathlib import Path
from datetime import datetime
from threading import Lock

from config import DATA_DIR
FILE_PATH = DATA_DIR / "scenarios.json"


class ScenarioService:
    """CU-13: What-If Simulator (JSON-backed)."""

    _lock = Lock()

    def __init__(self, prediction_service=None):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not FILE_PATH.exists():
            self._write([])
        # Lazy import to avoid circular dependency
        if prediction_service is None:
            from services.prediction_service import PredictionService
            prediction_service = PredictionService()
        self.prediction_service = prediction_service

    def _read(self):
        try:
            with FILE_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _write(self, items):
        with FILE_PATH.open("w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)

    def list_scenarios(self):
        return self._read()

    def get_scenario(self, scenario_id):
        for item in self._read():
            if item.get("id") == scenario_id:
                return item
        return None

    def create_scenario(self, payload):
        scenario = {
            "id": uuid.uuid4().hex[:12],
            "name": (payload.get("name") or "Scenario").strip(),
            "description": payload.get("description", ""),
            "target_race_id": payload.get("target_race_id"),
            "driver_id": payload.get("driver_id"),
            "constructor_id": payload.get("constructor_id"),
            "pace_delta": float(payload.get("pace_delta") or 0),
            "reliability_delta": float(payload.get("reliability_delta") or 0),
            "dnf_risk_delta": float(payload.get("dnf_risk_delta") or 0),
            "notes": payload.get("notes", ""),
            "grid_position": payload.get("grid_position"),
            "wet_race": bool(payload.get("wet_race", False)),
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        with self._lock:
            items = self._read()
            items.append(scenario)
            self._write(items)
        return scenario

    def delete_scenario(self, scenario_id):
        with self._lock:
            items = [s for s in self._read() if s.get("id") != scenario_id]
            self._write(items)
        return True

    def run_scenario(self, scenario_id):
        from services.season_service import SeasonContext
        scenario = self.get_scenario(scenario_id)
        if not scenario: raise ValueError('Scenario not found')
        next_race = SeasonContext().get()['next_race']
        race_id = scenario.get('target_race_id') or (next_race['race_id'] if next_race else None)
        if not race_id: raise ValueError('Select a scheduled race for this scenario')
        baseline = self.prediction_service.predict_race(int(race_id), persist=False)['predictions']
        changed = self.prediction_service.predict_race(int(race_id), scenario=scenario)['predictions']
        original = {p['driver_id']:p for p in baseline}
        diff = [{'driver_id':p['driver_id'], 'driver_name':p['driver_name'],
                 'baseline_probability':original[p['driver_id']]['win_probability'], 'scenario_probability':p['win_probability'],
                 'baseline_score':round(original[p['driver_id']]['win_probability']*100,2),
                 'scenario_score':round(p['win_probability']*100,2),
                 'delta':round((p['win_probability']-original[p['driver_id']]['win_probability'])*100,2)} for p in changed]
        return {'scenario':scenario,'baseline':baseline,'scenario_predictions':changed,'diff':sorted(diff,key=lambda d:abs(d['delta']),reverse=True),'note':'Hypothetical feature intervention; not a causal estimate. Regulations apply in the scenario layer.'}
