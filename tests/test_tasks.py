import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_task_crud(client):
    assert client.get("/tasks").json() == []
    response = client.post("/tasks", json={"title": " Learn ", "description": "Read"})
    assert response.status_code == 201
    task = response.json()
    assert task == {
        "id": task["id"], "title": "Learn", "description": "Read",
        "status": "todo", "priority": "medium",
    }
    url = f"/tasks/{task['id']}"
    assert client.get(url).json() == task
    assert client.get("/tasks").json() == [task]

    response = client.patch(url, json={"status": "done", "priority": "high"})
    assert response.status_code == 200
    updated = {**task, "status": "done", "priority": "high"}
    assert response.json() == updated
    assert client.get(url).json() == updated
    assert client.patch(url, json={}).json() == updated
    assert client.patch(url, json={"description": None, "title": "Done"}).json() == {
        **updated, "description": None, "title": "Done",
    }

    response = client.delete(url)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(url).status_code == 404
    assert client.get("/tasks").json() == []


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_task(client, method):
    kwargs = {"json": {"title": "New"}} if method == "patch" else {}
    response = getattr(client, method)("/tasks/999", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


@pytest.mark.parametrize("filters,expected", [
    ({}, ["A", "B", "C"]),
    ({"status": "todo"}, ["A", "B"]),
    ({"priority": "high"}, ["A", "C"]),
    ({"status": "todo", "priority": "high"}, ["A"]),
    ({"status": "done", "priority": "low"}, []),
])
def test_filters(client, filters, expected):
    for title, status, priority in [
        ("A", "todo", "high"), ("B", "todo", "low"), ("C", "done", "high"),
    ]:
        assert client.post("/tasks", json={
            "title": title, "status": status, "priority": priority,
        }).status_code == 201
    response = client.get("/tasks", params=filters)
    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == expected


@pytest.mark.parametrize("payload", [
    {"title": ""}, {"title": " \t\n"}, {"title": None}, {"title": 123},
    {"status": "invalid"}, {"priority": "urgent"},
    {"status": None}, {"priority": None}, {"description": 123}, {"unknown": True},
])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_invalid_input(client, payload, method):
    task = client.post("/tasks", json={"title": "Original"}).json()
    if method == "post":
        response = client.post("/tasks", json={"title": "New", **payload})
    else:
        response = client.patch(f"/tasks/{task['id']}", json=payload)
    assert response.status_code == 422
    assert client.get("/tasks").json() == [task]


def test_create_requires_title(client):
    assert client.post("/tasks", json={}).status_code == 422


@pytest.mark.parametrize("params", [{"status": "invalid"}, {"priority": "urgent"}])
def test_invalid_filters(client, params):
    assert client.get("/tasks", params=params).status_code == 422


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_invalid_id(client, method):
    kwargs = {"json": {}} if method == "patch" else {}
    assert getattr(client, method)("/tasks/not-an-id", **kwargs).status_code == 422
