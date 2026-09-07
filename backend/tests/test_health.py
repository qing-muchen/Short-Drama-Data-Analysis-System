"""Infrastructure-only health endpoint test."""

import asyncio

from httpx import ASGITransport, AsyncClient

from main import app


def test_health_check() -> None:
    async def request_health() -> tuple[int, dict[str, str]]:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/health")
            return response.status_code, response.json()

    status_code, body = asyncio.run(request_health())

    assert status_code == 200
    assert body == {"status": "ok"}
