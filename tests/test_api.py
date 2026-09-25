from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_add():
    r = client.post("/add", json={"a": 2, "b": 3})
    assert r.status_code == 200 and r.json()["result"] == 5


def test_subtract():
    assert client.post("/subtract", json={"a": 5, "b": 3}).json()["result"] == 2


def test_multiply():
    assert client.post("/multiply", json={"a": 4, "b": 2.5}).json()["result"] == 10


def test_divide():
    assert client.post("/divide", json={"a": 10, "b": 4}).json()["result"] == 2.5


def test_divide_by_zero():
    assert client.post("/divide", json={"a": 1, "b": 0}).status_code == 400


def test_invalid_input():
    assert client.post("/add", json={"a": "abc", "b": 1}).status_code == 422


def test_overflow():
    assert client.post("/multiply", json={"a": 1e308, "b": 10}).status_code == 422


def test_index_page():
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
