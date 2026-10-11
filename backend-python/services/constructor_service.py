from repositories.constructor_repository import ConstructorRepository


class ConstructorService:

    def __init__(self):
        self.repo = ConstructorRepository()

    def get_constructors(self):
        constructors = self.repo.get_all_constructors()
        return [constructor.to_dict() for constructor in constructors]

    def get_constructor(self, constructor_id):
        constructor = self.repo.get_constructor(constructor_id)
        if constructor:
            return constructor.to_dict()
        return None

    def create_constructor(self, constructor_data):
        constructor = self.repo.add_constructor(constructor_data)
        return constructor.to_dict()

    def update_constructor(self, constructor_id, constructor_data):
        constructor = self.repo.update_constructor(constructor_id, constructor_data)
        if constructor:
            return constructor.to_dict()
        return None

    def remove_constructor(self, constructor_id):
        self.repo.delete_constructor(constructor_id)