from repositories.driver_repository import DriverRepository


class DriverService:

    def __init__(self):
        self.repo = DriverRepository()

    def get_drivers(self):
        drivers = self.repo.get_all_drivers()
        return [driver.to_dict() for driver in drivers]

    def get_driver(self, driver_id):
        driver = self.repo.get_driver(driver_id)
        if driver:
            return driver.to_dict()
        return None

    def create_driver(self, driver_data):
        driver = self.repo.add_driver(driver_data)
        return driver.to_dict()

    def update_driver(self, driver_id, driver_data):
        driver = self.repo.update_driver(driver_id, driver_data)
        if driver:
            return driver.to_dict()
        return None

    def remove_driver(self, driver_id):
        self.repo.delete_driver(driver_id)