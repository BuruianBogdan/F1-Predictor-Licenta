from repositories.base_repository import Repository
from models.race import Race

class RaceRepository(Repository):
    def __init__(self):super().__init__(Race,'race_id')
    def get_all_races(self):return self.all()
    def get_race(self,entity_id):return self.get(entity_id)
    def add_race(self,data):return self.save(data)
    def update_race(self,entity_id,data):return self.save(data,entity_id)
    def delete_race(self,entity_id):return self.delete(entity_id)
