import pytest
from unittest.mock import patch, MagicMock
from app.aws.agents import PropertyAnalysisGraph, QueryAnalysis, AnalysisAgent, ANALYSIS_CACHE

async def fake_stream_async(*args, **kwargs):
    mock_events = [
        {
            "type": "multiagent_node_start",
            "node_id": "final_agent"
        },
        {
            "type": "multiagent_node_stream",
            "node_id": "final_agent",
            "event": {
                "data": "Some response"
            }
        }
    ]
    
    for event in mock_events:
        yield event

@pytest.mark.anyio
async def test_how_property_analysis_graph_handles_events():
    
    with patch("strands.multiagent.GraphBuilder.build") as mock_build:
        mock_graph = mock_build.return_value
        mock_graph.stream_async = MagicMock()
        mock_graph.stream_async.return_value = fake_stream_async()

        graph_instance = PropertyAnalysisGraph(query="test")
        yielded_items = []
        
        async for item in graph_instance.invoke_async():
            yielded_items.append(item)
        
        assert len(yielded_items) == 1
        assert "Some response" in yielded_items[0]

@pytest.mark.anyio
async def test_analysis_agent_cache_logic():
    agent = AnalysisAgent()
    
    ANALYSIS_CACHE.clear()
    
    from strands.agent import Agent
    with patch.object(Agent, 'stream_async', autospec=True) as mock_super_stream:
        mock_super_stream.return_value = fake_stream_async()
        
        state = {"user_query": "test"}
        async for _ in agent.stream_async(invocation_state=state):
            pass
        
        assert mock_super_stream.call_count == 1
        
        ANALYSIS_CACHE["test"] = {"fake": "data"}
        
        async for _ in agent.stream_async(invocation_state=state):
            pass
        
        assert mock_super_stream.call_count == 1

