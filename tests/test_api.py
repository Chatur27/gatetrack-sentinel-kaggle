from fastapi.testclient import TestClient

from backend.main import create_app


def test_health_endpoint():
    with TestClient(create_app(db_path=":memory:")) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_create_and_read_case(base_payload):
    with TestClient(create_app(db_path=":memory:")) as client:
        created = client.post("/api/visitors", json=base_payload)
        assert created.status_code == 201
        case_id = created.json()["case_id"]

        fetched = client.get(f"/api/visitors/{case_id}")
        assert fetched.status_code == 200
        assert fetched.json()["case_id"] == case_id

        audit = client.get(f"/api/audits/{case_id}")
        assert audit.status_code == 200
        assert len(audit.json()["events"]) >= 6
