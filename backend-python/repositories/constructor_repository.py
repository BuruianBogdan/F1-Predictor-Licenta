from repositories.base_repository import Repository
from models.constructor import Constructor

class ConstructorRepository(Repository):
    def __init__(self):super().__init__(Constructor,'constructor_id')
    def get_all_constructors(self):return self.all()
    def get_constructor(self,entity_id):return self.get(entity_id)
    def add_constructor(self,data):return self.save(data)
    def update_constructor(self,entity_id,data):return self.save(data,entity_id)
    def delete_constructor(self,entity_id):return self.delete(entity_id)
