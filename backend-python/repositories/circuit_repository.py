from repositories.base_repository import Repository
from models.circuit import Circuit

class CircuitRepository(Repository):
    def __init__(self):super().__init__(Circuit,'circuit_id')
    def get_all_circuits(self):return self.all()
    def get_circuit(self,entity_id):return self.get(entity_id)
    def add_circuit(self,data):return self.save(data)
    def update_circuit(self,entity_id,data):return self.save(data,entity_id)
    def delete_circuit(self,entity_id):return self.delete(entity_id)
