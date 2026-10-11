from sqlalchemy import Column, Integer, String
from database.db import Base


class Constructor(Base):
    __tablename__ = "constructors"

    constructor_id = Column(Integer, primary_key=True, autoincrement=True)
    constructor_ref = Column(String, unique=True)
    name = Column(String)
    nationality = Column(String)

    def to_dict(self):
        return {
            "constructor_id": self.constructor_id,
            "constructor_ref": self.constructor_ref,
            "name": self.name,
            "nationality": self.nationality,
        }