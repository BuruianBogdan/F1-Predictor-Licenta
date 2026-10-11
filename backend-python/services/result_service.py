from repositories.result_repository import ResultRepository


class ResultService:

    def __init__(self):
        self.repo = ResultRepository()

    def get_results(self):
        results = self.repo.get_all_results()
        return [result.to_dict() for result in results]

    def get_result(self, result_id):
        result = self.repo.get_result(result_id)
        if result:
            return result.to_dict()
        return None

    def create_result(self, result_data):
        result = self.repo.add_result(result_data)
        return result.to_dict()

    def update_result(self, result_id, result_data):
        result = self.repo.update_result(result_id, result_data)
        if result:
            return result.to_dict()
        return None

    def remove_result(self, result_id):
        self.repo.delete_result(result_id)