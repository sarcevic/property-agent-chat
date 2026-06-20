import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    """
    This fixture provides a configured TestClient instance 
    to your test functions automatically.
    """
    with TestClient(app) as c:
        yield c
