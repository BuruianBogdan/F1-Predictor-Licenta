from sqlalchemy import Column, Integer, String, Float
from database.db import Base


class Circuit(Base):
    __tablename__ = "circuits"

    circuit_id = Column(Integer, primary_key=True, autoincrement=True)
    circuit_ref = Column(String, unique=True)
    name = Column(String)
    location = Column(String)
    country = Column(String)
    lat = Column(Float)
    lng = Column(Float)

    def to_dict(self):
        return {
            "circuit_id": self.circuit_id,
            "circuit_ref": self.circuit_ref,
            "name": self.name,
            "location": self.location,
            "country": self.country,
            "lat": self.lat,
            "lng": self.lng
        }