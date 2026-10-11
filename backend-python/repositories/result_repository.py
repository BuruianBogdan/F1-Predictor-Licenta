from repositories.base_repository import Repository
from models.race_result import RaceResult

class ResultRepository(Repository):
    def __init__(self):super().__init__(RaceResult,'result_id')
    def get_all_results(self):return self.all()
    def get_result(self,entity_id):return self.get(entity_id)
    def add_result(self,data):return self.save(data)
    def update_result(self,entity_id,data):return self.save(data,entity_id)
    def delete_result(self,entity_id):return self.delete(entity_id)
    def get_results_by_race(self,race_id):
        from database.db import SessionLocal
        with SessionLocal() as s:return s.query(RaceResult).filter_by(race_id=race_id).all()
