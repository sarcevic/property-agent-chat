"""seed initial districts

Revision ID: e39a187be4e0
Revises: a577ddae561f
Create Date: 2026-06-03 16:42:47.301491

"""
import csv
import logging
import os

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = 'e39a187be4e0'
down_revision: Union[str, Sequence[str], None] = 'a577ddae561f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    
    try:
        bind = op.get_bind()
        result = bind.execute(sa.text("SELECT COUNT(*) FROM districts")).scalar()
        
        if result == 0:
            logger.info(f"Table districts is empty. Starting data import...")
            
            current_dir = os.path.dirname(__file__)
            csv_path = os.path.join(current_dir, 'districts.csv')
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = [row for row in reader]
                if rows:
                    meta = sa.MetaData()
                    table = sa.Table('districts', meta, autoload_with=bind)
                    bind.execute(table.insert(), rows)
                    logger.info(f"Successfully imported {len(rows)} rows.")
                else:
                    logger.info(f"Problem - rows empty")
        else:
            logger.info(f"Problem - result is {result}")
    
    except Exception as e:
        logger.info(f"Exception type: {type(e).__name__}")
        logger.info(f"Exception Message: {e}")

def downgrade() -> None:
    op.execute("TRUNCATE TABLE districts")
