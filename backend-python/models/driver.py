from sqlalchemy import Column, Integer, String, Date
from database.db import Base


class Driver(Base):
    __tablename__ = "drivers"

    driver_id = Column(Integer, primary_key=True, autoincrement=True)
    driver_ref = Column(String, unique=True)
    number = Column(Integer)
    code = Column(String)
    forename = Column(String)
    surname = Column(String)
    dob = Column(Date)
    nationality = Column(String)

    def to_dict(self):
        return {
            "driver_id": self.driver_id,
            "driver_ref": self.driver_ref,
            "number": self.number,
            "code": self.code,
            "forename": self.forename,
            "surname": self.surname,
            "dob": self.dob.isoformat() if self.dob else None,
            "nationality": self.nationality
        }