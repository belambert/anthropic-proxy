import pytest
import pytest_asyncio

from anthropic_proxy.server import create_app


@pytest_asyncio.fixture
async def client(aiohttp_client):
    """Create a test client for the proxy server."""
    app = await create_app(
        target_host="httpbin.org",
        target_scheme="https",
        show_headers=False,
        show_event_logging=False,
        show_tools=False,
        cache_json=True,
    )
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_proxy_forwards_request(client):
    """Test that the proxy forwards requests correctly."""
    resp = await client.get("/get")
    assert resp.status == 200


@pytest.mark.asyncio
async def test_proxy_forwards_post(client):
    """Test that the proxy forwards POST requests with body."""
    resp = await client.post("/post", json={"key": "value"})
    assert resp.status == 200
