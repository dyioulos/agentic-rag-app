import httpx
from .config import settings


async def list_models() -> list[str]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{settings.ollama_base_url}/api/tags")
        resp.raise_for_status()
        payload = resp.json()
        return [m["name"] for m in payload.get("models", [])]


async def generate(model: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
