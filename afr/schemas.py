"""This module defines the pydantic models that mirror the database schema, but with proper types and validation"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import uuid4

"""spans form a tree via parent_span_id, and the attributes bag is 
what lets one Span shape handle all the different span types."""


class SpanType(str, Enum):
    """Enum for span types."""
    LLM_CALL = "llm_call"
    TOOL_CALL = "TOOL_CALL"
    RETRIEVAL = "RETRIEVAL"
    GUARDRAIL = "GUARDRAIL"
    OTHER = "OTHER"

class RunStatus(str, Enum):
    """Enum for run status."""
    RUNNING = "RUNNING"
    SUCCESS = "success"
    ERROR = "ERROR"
#Plain strings stay portable across SQLite and Postgres and dodge migration pain when you add a span type.
#these are the pydantic models that mirror the database schema, but with proper types and validation. The API layer will use these models to validate incoming data and to serialize outgoing data, while the storage layer (db.py) will use the SQLAlchemy models which are more focused on how data is stored rather than how it's used in the application logic.
class Span(BaseModel):
    """Pydantic model for a span within a run."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    parent_span_id: Optional[str] = None
    type: SpanType  #already validated here
    name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    input: Optional[dict] = None
    output: Optional[dict] = None
    error: Optional[str] = None
    attributes: dict = Field(default_factory=dict)

class Run(BaseModel):
    """Pydantic model for a run."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_name: str
    status: RunStatus   #already validated here
    started_at: datetime
    ended_at: Optional[datetime] = None
    input: Optional[dict] = None
    output: Optional[dict] = None
    metadata: Optional[dict] = Field(default_factory=dict)
    spans: List[Span] = Field(default_factory=list)