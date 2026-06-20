from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    pass

class Area(Base):
    __tablename__ = "areas"
    
    postcode = Column(String(2), primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    embedding = Column(Vector(1024))
    
    districts = relationship("District", back_populates="area")

class District(Base):
    __tablename__ = "districts"
    
    postcode = Column(String(6), primary_key=True)
    category = Column(String(1), primary_key=True) # General, Flats, Houses, Detached, Semi-Detached, Terraced
    
    parent = Column(String(2), ForeignKey("areas.postcode"), nullable=False)
    post_town = Column(String(50), nullable=True)
    avg_price = Column(Integer, nullable=True)
    
    area = relationship("Area", back_populates="districts")
