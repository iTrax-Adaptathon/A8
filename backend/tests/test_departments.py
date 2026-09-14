def test_department_creation_and_list(client):
    payload = {"name": "Cardiology Unit", "code": "CARD"}
    res = client.post("/api/v1/departments", json=payload)
    assert res.status_code == 201
    dept = res.json()
    assert dept["name"] == "Cardiology Unit"
    assert dept["code"] == "CARD"

    list_res = client.get("/api/v1/departments")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
