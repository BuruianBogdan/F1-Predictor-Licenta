from repositories.base_repository import Repository
from models.driver import Driver

class DriverRepository(Repository):
    def __init__(self):super().__init__(Driver,'driver_id')
    def get_all_drivers(self):return self.all()
    def get_driver(self,entity_id):return self.get(entity_id)
    def add_driver(self,data):return self.save(data)
    def update_driver(self,entity_id,data):return self.save(data,entity_id)
    def delete_driver(self,entity_id):return self.delete(entity_id)
