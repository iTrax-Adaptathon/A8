def test_create_and_get_patient(client):
    payload = {
        "name": "Test Patient",
        "age": 35,
        "gender": "Male",
        "medical_record_number": "MRN-TEST-1",
    }
    res = client.post("/api/v1/patients", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Test Patient"
    assert data["current_status"] == "REGISTERED"

    patient_id = data["id"]
    get_res = client.get(f"/api/v1/patients/{patient_id}")
    assert get_res.status_code == 200
    assert get_res.json()["medical_record_number"] == "MRN-TEST-1"
