"""API contract: status codes, pagination, casing, OpenAPI, CORS."""
import re

from tests.helpers import create_bed, create_department, create_patient


def test_error_codes_and_shape(client):
    dept = create_department(client)
    # 404 with the common error body
    res = client.get("/api/v1/beds/9999")
    assert res.status_code == 404 and res.json() == {"error": "NOT_FOUND", "message": "Bed with id 9999 not found"}
    # 409 conflict
    bed = create_bed(client, dept["id"])
    res = client.patch(f"/api/v1/beds/{bed['id']}/status", json={"newStatus": "AVAILABLE"})
    assert res.status_code == 409 and res.json()["error"] == "CONFLICT" and res.json()["message"]
    # 422 pydantic validation
    res = client.post("/api/v1/patients", json={"name": "X", "age": -1, "gender": "F", "medicalRecordNumber": "M"})
    assert res.status_code == 422 and "detail" in res.json()
    # 422 domain validation
    res = client.post("/api/v1/beds", json={"bedNumber": "B", "departmentId": dept["id"], "status": "OCCUPIED"})
    assert res.status_code == 422 and res.json()["error"] == "DOMAIN_VALIDATION_ERROR"
    # 409 from a database unique constraint (duplicate MRN)
    create_patient(client, mrn="DUP-1")
    res = client.post("/api/v1/patients", json={"name": "Y", "age": 1, "gender": "F", "medicalRecordNumber": "DUP-1"})
    assert res.status_code == 409 and res.json()["error"] == "CONFLICT"
    assert client.get("/api/v1/patients").headers["X-Total-Count"] == "1"


def test_pagination_and_validation(client):
    dept = create_department(client)
    for i in range(5):
        create_bed(client, dept["id"], bed_number=f"P-{i}")
    res = client.get("/api/v1/beds", params={"limit": 2, "offset": 0})
    assert res.status_code == 200 and len(res.json()) == 2 and res.headers["X-Total-Count"] == "5"
    assert [b["bedNumber"] for b in res.json()] == ["P-0", "P-1"]
    res = client.get("/api/v1/beds", params={"limit": 2, "offset": 4})
    assert [b["bedNumber"] for b in res.json()] == ["P-4"] and res.headers["X-Total-Count"] == "5"
    assert client.get("/api/v1/beds", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/beds", params={"limit": 501}).status_code == 422
    assert client.get("/api/v1/beds", params={"offset": -1}).status_code == 422
    for path in ("/api/v1/patients", "/api/v1/departments", "/api/v1/theatres", "/api/v1/staff", "/api/v1/flow-events", "/api/v1/waitlist", "/api/v1/surgeries", "/api/v1/theatre-slots", "/api/v1/staff-assignments"):
        res = client.get(path, params={"limit": 1})
        assert res.status_code == 200 and "X-Total-Count" in res.headers and isinstance(res.json(), list), path


def test_camel_case_responses_and_snake_case_requests(client):
    dept = create_department(client)
    res = client.post("/api/v1/beds", json={"bed_number": "SNAKE-1", "bed_type": "ICU", "department_id": dept["id"]})
    assert res.status_code == 201
    body = res.json()
    assert body["bedNumber"] == "SNAKE-1" and body["bedType"] == "ICU" and body["departmentId"] == dept["id"]
    assert not any("_" in key for key in body)
    res = client.post("/api/v1/beds", json={"bedNumber": "CAMEL-1", "bedType": "ICU", "departmentId": dept["id"]})
    assert res.status_code == 201
    patient = create_patient(client)
    res = client.post(f"/api/v1/patients/{patient['id']}/admit", json={"department_id": dept["id"], "bed_id": body["id"]})
    assert res.status_code == 200 and res.json()["currentBedId"] == body["id"]
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", res.json()["admittedAt"])


def test_openapi_covers_all_groups(client):
    spec = client.get("/api/v1/openapi.json").json()
    paths = spec["paths"]
    expected = [
        "/api/v1/patients", "/api/v1/patients/{id}/history", "/api/v1/beds", "/api/v1/beds/{id}/release",
        "/api/v1/departments", "/api/v1/capacity", "/api/v1/flow-events", "/api/v1/theatres", "/api/v1/theatre-slots",
        "/api/v1/surgeries", "/api/v1/staff", "/api/v1/staff-assignments", "/api/v1/waitlist", "/api/v1/matches",
        "/api/v1/matches/confirm", "/api/v1/realtime",
    ]
    for path in expected:
        assert path in paths, path
    # schemas are camelCase
    bed_schema = spec["components"]["schemas"]["BedResponseSchema"]["properties"]
    assert "bedNumber" in bed_schema and "bed_number" not in bed_schema
    # actor headers are documented
    admit_params = paths["/api/v1/patients/{id}/admit"]["post"]["parameters"]
    assert {p["name"] for p in admit_params} >= {"X-Actor-ID", "X-Actor-Name"}
    assert "LLM" in spec["info"]["description"] and "deterministic" in spec["info"]["description"]
    assert client.get("/docs").status_code == 200


def test_cors_allows_configured_frontend_origin(client):
    res = client.options(
        "/api/v1/capacity",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
    res = client.get("/api/v1/beds", headers={"Origin": "http://localhost:5173"})
    assert res.headers["access-control-expose-headers"] == "X-Total-Count"
    res = client.options(
        "/api/v1/capacity",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in res.headers


def test_root_health(client):
    body = client.get("/").json()
    assert body["status"] == "online" and body["websocket"] == "/api/v1/ws/capacity"
