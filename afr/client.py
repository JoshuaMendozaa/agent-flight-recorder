from afr.schemas import Run
import httpx

async def post_run(run: Run, base_url: str = "http://localhost:8000") -> None:
    url = f"{base_url}/runs"
    payload = run.model_dump(mode="json")
    async with httpx.AsyncClient() as client:   #context manager
        #add timeout=
        response = await client.post(url, json=payload)
        response.raise_for_status()