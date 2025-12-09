import os
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine
from app.database import get_db  # ← THIS WAS THE MAIN BUG
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use a separate test database
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# Create test engine
TEST_ENGINE = create_engine(
    "sqlite:///./test.db",
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)

# Clean slate for every test run
Base.metadata.drop_all(bind=TEST_ENGINE)
Base.metadata.create_all(bind=TEST_ENGINE)

# Override the dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db  # ← Fixed: use the function directly

client = TestClient(app)


def test_create_request():
    payload = {
        "customer_name": "John Doe",
        "service_type": "Fuel Delivery",
        "location": "Makindye",
        "description": "Ran out of fuel"
    }
    response = client.post("/requests/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["customer_name"] == "John Doe"
    assert data["status"] == "pending"  # ← your model saves lowercase
    assert "id" in data


def test_get_all_requests():
    response = client.get("/requests/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_single_request():
    create_resp = client.post("/requests/", json={
        "customer_name": "Jane",
        "service_type": "Towing",
        "location": "Kampala",
        "description": "Engine dead"
    })
    request_id = create_resp.json()["id"]
    response = client.get(f"/requests/{request_id}")
    assert response.status_code == 200
    assert response.json()["id"] == request_id


def test_update_status():
    create_resp = client.post("/requests/", json={
        "customer_name": "Alice",
        "service_type": "Repair",
        "location": "Ntinda",
        "description": "Brakes issue"
    })
    request_id = create_resp.json()["id"]

    # ← Your endpoint uses PATCH + query param "status", not PUT + JSON
    response = client.patch(f"/requests/{request_id}/status", params={"status": "in-progress"})
    assert response.status_code == 200
    assert response.json()["status"] == "in-progress"


def test_delete_request():
    create_resp = client.post("/requests/", json={
        "customer_name": "Temp User",
        "service_type": "Test",
        "location": "Test",
        "description": "Will be deleted"
    })
    request_id = create_resp.json()["id"]

    response = client.delete(f"/requests/{request_id}")
    assert response.status_code == 200
    assert response.json()["detail"] == "Request deleted successfully"

    # Confirm gone
    resp = client.get(f"/requests/{request_id}")
    assert resp.status_code == 404