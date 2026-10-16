"""
API endpoint integration tests.

Uses FastAPI's TestClient (via httpx) to test the full request/response
cycle including database operations.
"""

import io

import numpy as np
import cv2
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from pathlib import Path
from app.main import app
from app.database import init_db, close_db
from app.config import get_settings

TEST_DB_PATH = Path("./data/test_memory.db")


@pytest_asyncio.fixture(scope="module")
async def client():
    """Create an async test client with an isolated test database."""
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


@pytest.fixture
def test_image_bytes():
    """Create a test image and encode it as JPEG bytes."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[100:300, 150:450] = (100, 180, 255)
    _, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /api/health should return system status."""
    response = await client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["project_name"] == "Cognitive Scene Memory"
    assert "model_name" in data
    assert "database_connected" in data
    assert "features" in data


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """GET / should return project info."""
    response = await client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["project"] == "Cognitive Scene Memory"
    assert "docs" in data


@pytest.mark.asyncio
async def test_process_image(client, test_image_bytes):
    """POST /api/process/image should run real YOLO and return detections."""
    files = {"file": ("test.jpg", io.BytesIO(test_image_bytes), "image/jpeg")}
    response = await client.post("/api/process/image", files=files)

    assert response.status_code == 200
    data = response.json()

    assert "scene_id" in data
    assert "detections" in data
    assert isinstance(data["detections"], list)
    assert "total_objects" in data
    assert "processing_time_ms" in data
    assert data["model_name"] == "yolov8n.pt"
    assert data["image_width"] == 640
    assert data["image_height"] == 480
    assert "annotated_image_url" in data


@pytest.mark.asyncio
async def test_process_invalid_file(client):
    """POST /api/process/image with invalid data should return 400."""
    files = {"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")}
    response = await client.post("/api/process/image", files=files)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_scenes(client):
    """GET /api/scenes should return a list."""
    response = await client.get("/api/scenes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_objects(client):
    """GET /api/objects should return a list."""
    response = await client.get("/api/objects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_scene_not_found(client):
    """GET /api/scenes/{invalid} should return 404."""
    response = await client.get("/api/scenes/NONEXISTENT")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_object_not_found(client):
    """GET /api/objects/{invalid} should return 404."""
    response = await client.get("/api/objects/NONEXISTENT")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_memory_endpoints(client):
    """Test GET /api/memory/summary, GET /api/memory/objects, and POST /api/memory/decay."""
    # Summary
    resp_sum = await client.get("/api/memory/summary")
    assert resp_sum.status_code == 200
    sum_data = resp_sum.json()
    assert "total_objects" in sum_data
    assert "active" in sum_data
    assert "average_confidence" in sum_data
    assert "timestamp" in sum_data

    # Objects
    resp_objs = await client.get("/api/memory/objects")
    assert resp_objs.status_code == 200
    assert isinstance(resp_objs.json(), list)

    # Decay
    resp_decay = await client.post("/api/memory/decay")
    assert resp_decay.status_code == 200
    decay_data = resp_decay.json()
    assert "message" in decay_data
    assert "decayed" in decay_data


@pytest.mark.asyncio
async def test_scene_graph_endpoints(client):
    """Test Scene Graph endpoints."""
    # First get scenes
    resp_scenes = await client.get("/api/scenes")
    scenes = resp_scenes.json()
    if scenes:
        scene_id = scenes[0]["scene_id"]

        # GET scene graph
        resp_graph = await client.get(f"/api/scene-graph/{scene_id}")
        assert resp_graph.status_code == 200
        graph_data = resp_graph.json()
        assert graph_data["scene_id"] == scene_id
        assert "nodes" in graph_data
        assert "edges" in graph_data
        assert "node_count" in graph_data
        assert "edge_count" in graph_data

        # POST rebuild scene graph
        resp_build = await client.post(f"/api/scene-graph/{scene_id}/build")
        assert resp_build.status_code == 200

        # GET relationships
        resp_rels = await client.get(f"/api/scene-graph/{scene_id}/relationships")
        assert resp_rels.status_code == 200
        assert isinstance(resp_rels.json(), list)

    # 404 for non-existent scene
    resp_404 = await client.get("/api/scene-graph/NONEXISTENT")
    assert resp_404.status_code == 404


@pytest.mark.asyncio
async def test_changes_endpoints(client):
    """Test Change Detection endpoints."""
    # GET recent changes
    resp_recent = await client.get("/api/changes/recent")
    assert resp_recent.status_code == 200
    assert isinstance(resp_recent.json(), list)

    # Check comparison with non-existent scenes returns 404
    resp_cmp_404 = await client.post(
        "/api/changes/compare",
        json={"scene_before_id": "FAKE1", "scene_after_id": "FAKE2"},
    )
    assert resp_cmp_404.status_code == 404

    # Check for real scene if available
    resp_scenes = await client.get("/api/scenes")
    scenes = resp_scenes.json()
    if scenes:
        scene_id = scenes[0]["scene_id"]
        # Comparison of scene with itself
        resp_cmp = await client.post(
            "/api/changes/compare",
            json={"scene_before_id": scene_id, "scene_after_id": scene_id},
        )
        assert resp_cmp.status_code == 200
        cmp_data = resp_cmp.json()
        assert cmp_data["scene_before_id"] == scene_id
        assert cmp_data["scene_after_id"] == scene_id
        assert "total_changes" in cmp_data

        # Scene changes
        resp_scene_changes = await client.get(f"/api/changes/scene/{scene_id}")
        assert resp_scene_changes.status_code == 200
        assert isinstance(resp_scene_changes.json(), list)

