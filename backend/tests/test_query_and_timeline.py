"""
Unit and integration tests for Query Chatbot, Timeline, and Settings endpoints.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from app.main import app
from app.database import init_db, close_db
from app.config import get_settings

TEST_DB_PATH = Path("./data/test_query_timeline.db")


@pytest_asyncio.fixture(scope="module")
async def client():
    settings = get_settings()
    original_db_url = settings.database_url
    settings.database_url = f"sqlite:///{TEST_DB_PATH.as_posix()}"

    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_db()

    settings.database_url = original_db_url
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_settings_endpoints(client):
    """Test GET and PATCH /api/settings."""
    # GET settings
    res = await client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "confidence_threshold" in data
    assert "model_name" in data

    # PATCH settings
    res_patch = await client.patch("/api/settings", json={"confidence_threshold": 0.45})
    assert res_patch.status_code == 200
    updated = res_patch.json()
    assert updated["confidence_threshold"] == 0.45


@pytest.mark.asyncio
async def test_timeline_endpoint(client):
    """Test GET /api/timeline."""
    res = await client.get("/api/timeline")
    assert res.status_code == 200
    data = res.json()
    assert "total_events" in data
    assert "events" in data
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_query_chatbot_endpoint(client):
    """Test POST /api/query chatbot answers."""
    # Query overview
    res = await client.post("/api/query", json={"query": "Overview of the room"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert data["confidence"] > 0.0

    # Query comparison without enough scenes
    res_comp = await client.post("/api/query", json={"query": "Compare scene 1 and scene 2"})
    assert res_comp.status_code == 200
    assert "compare" in res_comp.json()["answer"].lower() or "scene" in res_comp.json()["answer"].lower()

    # Query location
    res_loc = await client.post("/api/query", json={"query": "Where is the chair?"})
    assert res_loc.status_code == 200
    assert "answer" in res_loc.json()


@pytest.mark.asyncio
async def test_natural_language_spatial_relations():
    """Verify natural conversational sentence synthesis instead of raw uppercase tokens."""
    from app.services.query_service import (
        _join_natural_list,
        _fuzzy_match_token,
        _extract_coordinates,
        RELATION_PHRASES,
    )

    # Test joining phrases
    assert _join_natural_list(["to the right of the bucket", "behind the box"]) == "to the right of the bucket and behind the box"
    assert _join_natural_list(["A", "B", "C"]) == "A, B, and C"

    # Test typo tolerance
    assert _fuzzy_match_token("char", ["chair", "table", "laptop"]) == "chair"
    assert _fuzzy_match_token("laptp", ["chair", "table", "laptop"]) == "laptop"

    # Test preposition mapping
    assert RELATION_PHRASES["RIGHT_OF"] == "to the right of the"
    assert RELATION_PHRASES["BEHIND"] == "behind the"

    # Test coordinate extraction
    assert _extract_coordinates("what all was near the person at (172,357)") == (172.0, 357.0)
    assert _extract_coordinates("what is at (172, 357)") == (172.0, 357.0)
    assert _extract_coordinates("objects near at 100.5, 200.5") == (100.5, 200.5)


@pytest.mark.asyncio
async def test_coordinate_query_endpoint(client):
    """Test coordinate-based query endpoint handles coordinates properly."""
    res = await client.post("/api/query", json={"query": "what all was near the person at (172,357)"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert data["confidence"] > 0.0


