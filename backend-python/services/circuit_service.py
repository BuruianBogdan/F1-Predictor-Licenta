"""Resolution-independent circuit geometry, matched to real circuit identity."""
import json
from functools import lru_cache
from pathlib import Path
from database.db import SessionLocal
from models.race import Race
from models.circuit import Circuit
from services.season_service import SeasonContext,utcnow,race_start

@lru_cache(maxsize=1)
def layouts():
    path=Path(__file__).resolve().parents[1]/'resources/circuit_layouts.json'
    return json.loads(path.read_text()) if path.exists() else {}

class CircuitPresentationService:
    def present(self,circuit):
        if circuit is None:return {'name':'Circuit to be confirmed','layout_available':False}
        info=layouts().get(circuit.circuit_ref,{})
        return {**circuit.to_dict(),**info,'layout_available':bool(info),'layout_note':'Current reference layout; historical configurations may differ'}
    def calendar(self,season=None):
        context=SeasonContext().get();season=season or context['active_season'];now=utcnow()
        with SessionLocal() as s:
            rows=s.query(Race,Circuit).outerjoin(Circuit,Circuit.circuit_id==Race.circuit_id).filter(Race.season_year==season).all()
        upcoming=[];completed=[];pending=[];other=[]
        for race,circuit in rows:
            item={**race.to_dict(),'circuit':self.present(circuit)}
            if race.race_status in ('CANCELLED','POSTPONED'):other.append(item)
            elif race.is_completed and race.results_verified:completed.append(item)
            elif race.date and race_start(race)>now:upcoming.append(item)
            else:pending.append(item)
        upcoming.sort(key=lambda r:(r['date'] or '',r['round']))
        completed.sort(key=lambda r:(r['date'] or '',r['round']),reverse=True)
        pending.sort(key=lambda r:(r['date'] or '',r['round']))
        return {'context':context,'season':season,'upcoming':upcoming,'completed':completed,'pending':pending,'other':other,'next':upcoming[0] if upcoming else None,'total':len(rows),'completed_count':len(completed),'remaining_count':len(upcoming)}


from repositories.circuit_repository import CircuitRepository


class CircuitService:

    def __init__(self):
        self.repo = CircuitRepository()

    def get_circuits(self):
        circuits = self.repo.get_all_circuits()
        return [circuit.to_dict() for circuit in circuits]

    def get_circuit(self, circuit_id):
        circuit = self.repo.get_circuit(circuit_id)
        if circuit:
            return circuit.to_dict()
        return None

    def create_circuit(self, circuit_data):
        circuit = self.repo.add_circuit(circuit_data)
        return circuit.to_dict()

    def update_circuit(self, circuit_id, circuit_data):
        circuit = self.repo.update_circuit(circuit_id, circuit_data)
        if circuit:
            return circuit.to_dict()
        return None

    def remove_circuit(self, circuit_id):
        self.repo.delete_circuit(circuit_id)
