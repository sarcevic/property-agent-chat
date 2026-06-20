import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")

class DatabaseManager:
    def __init__(self, url: str):
        self.engine = create_engine(
            url,
            pool_size = 5,
            max_overflow = 10,
            pool_pre_ping = True
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def get_session(self) -> Session:
        pool = self.engine.pool
        logger.info(f"get_session, Pool size: {pool.size()}, Idle Connections: {pool.checkedin()}, Active connections {pool.checkedout()}, Overflow: {pool.overflow()}")
        return self.SessionLocal()

db_manager = DatabaseManager(DATABASE_URL)
