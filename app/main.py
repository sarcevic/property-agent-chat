import asyncio
import logging
import os
import time

from alembic.config import Config
from alembic import command
from app.database.session import db_manager
from app.database.models import Area
from app.aws.agents import PropertyAnalysisGraph
from app.aws.models import getEmbeddings
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations():
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("skip_logging", "True")
    command.upgrade(alembic_cfg, "head")

def hydrate_embeddings():
    # This is lazy hydration. We call Ollama to generate embeddings for areas.
    time.sleep(1)
    try:
        session = db_manager.get_session()
        logger.info("DB session acquired...")
        stmt = select(Area).where(Area.embedding == None)
        # Execute statement and iterate over the resulting scalar values
        for area in session.scalars(stmt):
            time.sleep(0.1)
            logger.info(f"Generating embedding for area {area.postcode}")
            area.embedding = getEmbeddings(area.description)
            session.commit()
            logger.info(f"Area {area.postcode} done.")
    except Exception as e:
        session.rollback()
        logger.info(f"Hydration failed: {e}")
    finally:
        session.close()
        logger.info("DB session closed and returned to pool")

@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, hydrate_embeddings)
    yield

app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html"
    )

@app.get("/ask")
async def ask(query: str):
    propertyAnalysisGraph = PropertyAnalysisGraph(query)
    return StreamingResponse(propertyAnalysisGraph.invoke_async(), media_type="text/event-stream")
