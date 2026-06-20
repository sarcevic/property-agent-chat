import json
import logging
import time

from sqlalchemy import select
from pydantic import BaseModel, Field
from strands import Agent
from strands.agent.agent_result import AgentResult
from strands.hooks import AfterInvocationEvent
from strands.telemetry.metrics import EventLoopMetrics
from strands.multiagent import GraphBuilder
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
from strands.types._events import AgentResultEvent
from strands.types.agent import AgentInput
from strands.types.content import ContentBlock, Message
from typing import Literal, Any, AsyncIterator

from ..database.session import db_manager
from ..database.models import Area, District
from .models import gemma4_e4b_model, getEmbeddings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ANALYSIS_AGENT_PROMPT = """
You are a query parser.
Your goal is to extract search parameters from the user query.
Do not evaluate, answer, or reply to the user text.
"""

PROPERTIES_AGENT_PROMPT = """
You are real estate assistant. Your job is to suggest areas found by areas_agent.

RULES:
1. Output raw HTML without markdowns.
2. Use this template for each area:
   <h3>{Area Name}</h3>
   <p>{Single sentence about this area}</p>
3. Do not add introductory or concluding sentences outside of this HTML template.
4. If areas_agent returned empty list, just say we could not find results for provided filters.
"""


class QueryAnalysis(BaseModel):
    area_description: str = Field(description="Description of area (lifestyle, climate, vibes, etc). If no relevant content found, set 'area_description' to empty string.")
    min_price: int = Field(description="The lower numerical bound. e.g., 100000. If no number is mentioned, set 'min_price' to 0.")
    max_price: int = Field(description="The upper numerical bound. e.g., 800000. If no number is mentioned, set 'max_price' to 0.")
    price_logic: Literal["STRICT", "AROUND", "NONE"] = Field(
        description=(
            "STRICT: For ranges or 'under/over' limits. "
            "AROUND: For 'approx', 'around', 'about', or 'roughly'. "
            "NONE: No price mentioned."
        )
    )
    price_sort: Literal["CHEAPEST", "EXPENSIVE", "NONE"] = Field(
        description=(
            "CHEAPEST: user said 'cheap', 'budget', 'affordable', or 'bargain'. "
            "EXPENSIVE: user said 'expensive', 'luxury', 'exclusive', or 'high-end'. "
            "NONE: no relative price descriptors used."
        )
    )

ANALYSIS_CACHE = {}

class AnalysisAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(
            name="analysis_agent",
            model=gemma4_e4b_model,
            system_prompt=ANALYSIS_AGENT_PROMPT,
            structured_output_model=QueryAnalysis,
            **kwargs
        )
    
    async def stream_async(
        self,
        prompt: AgentInput = None,
        *,
        invocation_state: dict[str, Any] | None = None,
        structured_output_model: type[BaseModel] | None = None,
        structured_output_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        logger.info(f"AnalysisAgent stream_async, checking cache: {len(ANALYSIS_CACHE)}")
        user_query = (invocation_state.get("user_query")).lower()
        if user_query in ANALYSIS_CACHE:
            logger.info("Cache Hit: Skipping LLM for Analysis")
            empty_result = AgentResult(
                stop_reason="end_turn",
                message=Message(role="assistant", content=[]),
                metrics=EventLoopMetrics(),
                state={},
            )
            yield AgentResultEvent(result=empty_result).as_dict()
            return
        
        async for event in super().stream_async(
            prompt=prompt,
            invocation_state=invocation_state,
            structured_output_model=structured_output_model,
            structured_output_prompt=structured_output_prompt,
            **kwargs
        ):
            yield event

class EmbeddingMultiAgent(MultiAgentBase):
    def __init__(self):
        self.name = "embedding_agent"
        super().__init__()
    
    async def invoke_async(self, task, invocation_state, **kwargs):
        try:
            user_query = (invocation_state.get("user_query")).lower()
            if user_query in ANALYSIS_CACHE:
                structured_data = ANALYSIS_CACHE[user_query]
                invocation_state["structured_data"] = structured_data
            else:
                structured_data = invocation_state.get("structured_data")
                ANALYSIS_CACHE[user_query] = structured_data
            
            embedding = getEmbeddings((structured_data["area_description"]).lower())
            invocation_state["embedding"] = embedding
            agent_result = AgentResult(
                stop_reason="end_turn",
                message=Message(role="assistant", content=[]),
                metrics=EventLoopMetrics(),
                state={},
            )
            return MultiAgentResult(
                status = Status.COMPLETED,
                results={self.name: NodeResult(result=agent_result)}
            )
        except Exception as e:
            logger.info(f"Exception {e}")
            return MultiAgentResult(
                status = Status.FAILED,
                results={e}
            )

class AreasMultiAgent(MultiAgentBase):
    def __init__(self):
        self.name = "areas_agent"
        super().__init__()

    async def stream_async(
        self, 
        task: Any, 
        invocation_state: dict[str, Any] | None = None, 
        **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            embedding = invocation_state.get("embedding")
            structured_data = invocation_state.get("structured_data")
            user_query = (invocation_state.get("user_query")).lower()
            
            session = db_manager.get_session()
            statement = (
                select(Area)
                .order_by(Area.embedding.cosine_distance(embedding))
                .limit(10)
            )
            areas = session.scalars(statement).all()
            selected_areas = []
            
            for area in areas:
                logger.info(f"AREA {area.name} found.")
                
                # Starting statement:
                statement = (
                    select(District)
                    .where(District.parent == area.postcode)
                    .limit(5)
                )
                
                # Extend with mentioned property type: General, Flats, Houses, Detached, Semi-Detached, Terraced
                if "flat" in user_query:
                    statement = statement.where(District.category == "F")
                elif "terraced" in user_query:
                    statement = statement.where(District.category == "T")
                elif "semi-detached" in user_query:
                    statement = statement.where(District.category == "S")
                elif "detached" in user_query:
                    statement = statement.where(District.category == "D")
                elif "house" in user_query:
                    statement = statement.where(District.category == "H")
                else:
                    statement = statement.where(District.category == "G")
                
                # Extend with structured_data rules
                if(structured_data.get("price_logic") == "STRICT"):
                    if(structured_data.get("max_price") == structured_data.get("min_price")):
                        statement = statement.where(District.avg_price <= 1.1*structured_data.get("max_price"))
                        statement = statement.where(District.avg_price >= 0.9*structured_data.get("min_price"))
                    else:
                        if(structured_data.get("max_price")):
                            statement = statement.where(District.avg_price <= structured_data.get("max_price"))
                        if(structured_data.get("min_price")):
                            statement = statement.where(District.avg_price >= structured_data.get("min_price"))
                
                elif(structured_data.get("price_logic") == "AROUND"):
                    statement = statement.where(District.avg_price <= 1.1*structured_data.get("max_price"))
                    statement = statement.where(District.avg_price >= 0.9*structured_data.get("min_price"))
                
                if(structured_data.get("price_sort") == "EXPENSIVE"):
                    statement = statement.order_by(District.avg_price.desc())
                else:
                    statement = statement.order_by(District.avg_price)
                
                # Query for districts
                districts = session.scalars(statement).all()
                
                for district in districts:
                    logger.info(f"    District {district.postcode} in {district.post_town} found. Avg price: {district.avg_price}.")
                    yield {
                        "data": f"{area.name},{district.postcode},{district.category},{district.post_town},{district.avg_price};"
                    }
                
                if not districts:
                    logger.info(f"Could not find any district for {area.name} and selected filters.")
                else:
                    selected_areas.append(area.name)
                    if(len(selected_areas) == 5):
                        break
            
            if selected_areas:
                yield {"data": "|"} # signal to frontend that we are done with districts
            
            result_string = ", ".join(selected_areas)
            
            agent_result = AgentResult(
                stop_reason="end_turn",
                message=Message(role="assistant", content=[ContentBlock(text=result_string)]),
                metrics=EventLoopMetrics(),
                state={},
            )
            return_value = MultiAgentResult(
                status = Status.COMPLETED,
                results={self.name: NodeResult(result=agent_result)}
            )
        except Exception as e:
            return_value = MultiAgentResult(
                status = Status.FAILED,
                results={e}
            )
        finally:
            session.close()
        
        yield {"result": return_value}
    
    async def invoke_async(self, task, invocation_state, **kwargs):
        pass

class FinalAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(
            name="final_agent",
            model=gemma4_e4b_model,
            system_prompt=PROPERTIES_AGENT_PROMPT,
            **kwargs
        )


async def on_after_invoke(event: AfterInvocationEvent):
    structured_data = event.result.to_dict()
    if structured_data:
        event_input = structured_data['message']['content'][0]['toolUse']['input']
        event.invocation_state["structured_data"] = event_input
        logger.info(f"Hook log: Saved {event_input} to invocation_state.")

class PropertyAnalysisGraph:
    def __init__(self, query: str):
        self.query = query
        self.builder = GraphBuilder()
        self.analysisAgent = AnalysisAgent()
        self.embeddingMultiAgent = EmbeddingMultiAgent()
        self.areasMultiAgent = AreasMultiAgent()
        self.finalAgent = FinalAgent()
        
        self.analysisAgent.add_hook(on_after_invoke)
        
        self.builder.add_node(self.analysisAgent, "analysis_agent")
        self.builder.add_node(self.embeddingMultiAgent, "embedding_agent")
        self.builder.add_node(self.areasMultiAgent, "areas_agent")
        self.builder.add_node(self.finalAgent, "final_agent")
        
        self.builder.add_edge("analysis_agent", "embedding_agent")
        self.builder.add_edge("embedding_agent", "areas_agent")
        self.builder.add_edge("areas_agent", "final_agent")
        
        self.builder.set_entry_point("analysis_agent")
        self.builder.set_execution_timeout(120)
        self.graph = self.builder.build()
        
        self.start_time = 0
    
    async def invoke_async(self):
        try:
            shared_state = {
                "user_query": self.query
            }
            async for event in self.graph.stream_async(self.query, invocation_state=shared_state):
                if event.get("type") == "multiagent_node_start":
                    logger.info(f"Node {event['node_id']} starting at {int(time.time())}")
                    self.start_time = time.time()
                
                elif event.get("type") == "multiagent_node_stream":
                    inner_event = event["event"]
                    if "data" in inner_event and inner_event["data"]:
                        event_data = inner_event["data"]
                        data_type = event["node_id"].split('_')[0]
                        chunk = {
                            "data_type": data_type,
                            "event_data": event_data
                        }
                        json_string = json.dumps(chunk) + "\n"
                        
                        # logger.info(f"Streaming the data: {json_string}")
                        yield json_string
                
                elif event.get("type") == "multiagent_node_stop":
                    node_result = event["node_result"]
                    logger.info(f"Node {event['node_id']} completed: {node_result.status} in {int(int(time.time())-self.start_time)}")
                
                elif event.get("type") == "multiagent_result":
                    result = event["result"]
                    logger.info(f"Graph completed: {result.status}")

        except Exception as e:
            yield f"Error: {str(e)}"
