"""afr/api.py -- ingestion + retrieval API (FastAPI).

  POST /runs        record a full run (with spans)
  GET  /runs        list runs (summary)
  GET  /runs/{id}   read one run back
Run it:  uvicorn afr.api:app --reload
"""
from fastapi import FastAPI, HTTPException
from typing import List
from afr.db import SessionLocal, init_db, RunRow, SpanRow
from afr.schemas import Run, Span
from sqlalchemy.exc import NoResultFound
from contextlib import asynccontextmanager
from sqlalchemy import select

def _row_to_schema(row: RunRow) -> Run:
    """Helper function to convert a RunRow to a Run schema."""
    return Run(
        id=row.id,
        agent_name=row.agent_name,
        status=row.status,
        started_at=row.started_at,
        ended_at=row.ended_at,
        input=row.input,
        output=row.output,
        metadata=row.run_metadata,
        spans=[Span(
            id=span_row.id,
            parent_span_id=span_row.parent_span_id,
            type=span_row.type,
            name=span_row.name,
            started_at=span_row.started_at,
            ended_at=span_row.ended_at,
            input=span_row.input,
            output=span_row.output,
            error=span_row.error,
            attributes=span_row.attributes
        ) for span_row in row.spans]
    )

@asynccontextmanager #what does contextmanager do? It allows you to define setup and teardown logic for resources, in this case, initializing the database when the application starts. The code before the yield is executed when the application starts, and the code after the yield is executed when the application shuts down. This ensures that the database is initialized before any requests are handled.
async def lifespan(app: FastAPI):
    """Lifespan context manager to initialize the database on startup."""
    init_db()
    yield

app = FastAPI(
    title="Agentic Feedback Recorder (AFR) API",
    description="API for recording and retrieving agentic feedback runs and spans.",
    version="0.1.0",
    lifespan=lifespan # this tells FastAPI to use the lifespan context manager we defined above, which will initialize the database when the application starts.
)

@app.post("/runs", response_model=Run)
def create_run(run: Run):
    """Create a new run with spans"""
    with SessionLocal() as session:
        row = RunRow(
            id=run.id,
            agent_name=run.agent_name,
            status=run.status.value,  # store enum value as string
            run_metadata=run.metadata,  # Pydantic 'metadata' field maps to 'run_metadata' in the database
            started_at=run.started_at,
            ended_at=run.ended_at,
            input=run.input,
            output=run.output,
            spans=[SpanRow(
                id=span.id,
                parent_span_id=span.parent_span_id,
                type=span.type.value,  # store enum value as string
                name=span.name,
                started_at=span.started_at,
                ended_at=span.ended_at,
                input=span.input,
                output=span.output,
                error=span.error,
                attributes=span.attributes
            ) for span in run.spans]
        )
        session.add(row)
        session.commit()
        return run

@app.get("/runs", response_model=List[Run])
def list_runs():
    """List all runs (without spans for summary)"""
    with SessionLocal() as session:
        rows = session.scalars(select(RunRow)).all()
        return [Run(
            id=row.id,
            agent_name=row.agent_name,
            status=row.status,
            started_at=row.started_at,
            ended_at=row.ended_at,
            input=row.input,
            output=row.output,
            metadata=row.run_metadata
        ) for row in rows]

@app.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str):
    """Get a run by ID, including spans"""
    with SessionLocal() as session:
        try:
            row = session.get(RunRow, run_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Run not found")
            return _row_to_schema(row)
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Run not found")