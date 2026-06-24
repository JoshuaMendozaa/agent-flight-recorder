import asyncio
from pathlib import Path
from dotenv import load_dotenv
from claude_agent_sdk import (
    query, ClaudeAgentOptions
)

from afr.tracer import record_run
from afr.client import post_run

load_dotenv(dotenv_path=".env") #load environment variables from .env file

async def main() -> None:
    options = ClaudeAgentOptions(
        allowed_tools=["Bash", "Read", "Glob"],
        permission_mode="acceptEdits", #dont pause for confirmations
        cwd=".",
    )
    Task = "List the python files in this project and briefly describe what each does."
    run = await record_run(agent_name="subject_agent", task=Task, options=options)

    # M1.2: dump the assembled trace so we can eyeball the span tree.
    trace_dir = Path("traces")
    trace_dir.mkdir(exist_ok=True)
    trace_path = trace_dir / f"{run.id}.json"
    trace_path.write_text(run.model_dump_json(indent=2))
    print(f"trace saved to {trace_path}")

    await post_run(run)
    print(f"run landed")


if __name__ == "__main__":
    asyncio.run(main())