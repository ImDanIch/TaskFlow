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


@pytest.mark.parametrize("params,expected_indexes", [
    ({}, [0, 1, 2, 3]),
    ({"limit": 2}, [0, 1]),
    ({"offset": 1}, [1, 2, 3]),
    ({"offset": 1, "limit": 2}, [1, 2]),
    ({"limit": 1}, [0]),
    ({"limit": 100}, [0, 1, 2, 3]),
    ({"offset": 4, "limit": 2}, []),
    ({"offset": 100}, []),
    ({"offset": 2**63 - 1}, []),
])
def test_pagination(client, params, expected_indexes):
    tasks = []
    for title in ["D", "B", "A", "C"]:
        response = client.post("/tasks", json={"title": title})
        assert response.status_code == 201
        tasks.append(response.json())
    response = client.get("/tasks", params=params)
    assert response.status_code == 200
    assert response.json() == [tasks[index] for index in expected_indexes]


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": -1}, {"limit": 101}, {"limit": "abc"},
    {"limit": "1.5"}, {"offset": -1}, {"offset": "abc"}, {"offset": "1.5"},
    {"offset": 2**63}, {"offset": 10**100},
])
def test_invalid_pagination(client, params):
    assert client.get("/tasks", params=params).status_code == 422


def test_pagination_empty_list(client):
    response = client.get("/tasks", params={"offset": 1, "limit": 1})
    assert response.status_code == 200
    assert response.json() == []


def test_pagination_applies_after_both_filters(client):
    tasks = []
    for title, status, priority in [
        ("A", "done", "high"), ("B", "todo", "high"),
        ("C", "todo", "low"), ("D", "todo", "high"),
        ("E", "todo", "high"),
    ]:
        response = client.post("/tasks", json={
            "title": title, "status": status, "priority": priority,
        })
        assert response.status_code == 201
        tasks.append(response.json())
    response = client.get("/tasks", params={
        "status": "todo", "priority": "high", "offset": 1, "limit": 1,
    })
    assert response.status_code == 200
    assert response.json() == [tasks[3]]
