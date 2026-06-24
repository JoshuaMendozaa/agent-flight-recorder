"""Database models and init logic using SQLAlchemy. This is the storage layer that defines how data is stored in the database, and it uses SQLAlchemy's ORM to map Python classes to database tables. The API layer (api.py) will use these models to interact with the database, while the schemas (schemas.py) define the data structures used for validation and serialization at the API boundary."""
from sqlalchemy import create_engine, String, DateTime, JSON, ForeignKey, Integer
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship, mapped_column, Mapped
from typing import Optional
import os
import datetime


engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///afr.db"), echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)    #this is the factory for creating new database sessions. Whenever we want to interact with the database, we will create a new session using this factory, which ensures that we have a fresh session for each request or operation.

class Base(DeclarativeBase):
    pass

def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)

# why status(and type) is string? pydantic already validates it at api boundary, and this is just a storage layer, so we can store the enum value directly as a string without needing to worry about serialization/deserialization of the enum itself. This keeps the storage layer simple and decoupled from the specific implementation details of the API layer.
class RunRow(Base): #why Row? to distinguish from the pydantic models in schemas.py. The "Row" suffix indicates that these are the SQLAlchemy ORM models that represent rows in the databaase tables, while the models in schemas.py are the Pydantic models used for validation and serialization at the API boundary. This naming convention helps to keep the two layers clear and organized.
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # store enum value as string
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    run_metadata: Mapped[dict] = mapped_column(JSON, default=dict) # this is the flexible bag for run-specific data
    spans: Mapped[list["SpanRow"]] = relationship("SpanRow", back_populates="run", cascade="all, delete-orphan", order_by="SpanRow.sequence")

class SpanRow(Base):
    __tablename__ = "spans"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("runs.id"))
    parent_span_id: Mapped[Optional[str]] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)  # store enum value as string
    name: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    input: Mapped[Optional[dict]] = mapped_column(JSON)
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)   # this is the flexible bag for span-specific data
    run: Mapped["RunRow"] = relationship("RunRow", back_populates="spans")
    sequence: Mapped[int] = mapped_column(Integer)