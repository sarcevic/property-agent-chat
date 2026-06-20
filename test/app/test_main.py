import pytest
from unittest.mock import patch

def test_homepage(client):
    """A basic test to see if your home page loads"""
    response = client.get("/")
    assert response.status_code == 200

async def fake_stream_async(*args, **kwargs):
    yield {"output": "Mocked AI thought..."}
    yield {"output": "Final mock answer."}

def test_ask_endpoint_with_mocked_ollama(client):
    
    with patch("strands.multiagent.GraphBuilder.build") as mock_build:
        mock_graph = mock_build.return_value
        mock_graph.stream_async = fake_stream_async
        response = client.get("/ask", params={"query": "test query"})
        assert response.status_code == 200
