"""seed initial areas

Revision ID: f8ce44dc39eb
Revises: 38ad62b1b89d
Create Date: 2026-04-29 15:55:04.286589

"""
import json
import logging
import os

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = 'f8ce44dc39eb'
down_revision: Union[str, Sequence[str], None] = '38ad62b1b89d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    
    try:
        areas_content = []
        current_dir = os.path.dirname(__file__)
        areas_path = os.path.join(current_dir, 'areas.txt')
        
        with open(areas_path) as areas_file:
            while True:
                lines = [areas_file.readline() for _ in range(4)]
                if not any(lines) or len(lines) != 4:
                    break
                line1, line2, line3, line4 = [l.strip() for l in lines]
                embedding_list = json.loads(line4) if line4 and line4 != "[]" else None
                item = {
                    "postcode": line1,
                    "name": line2,
                    "description": line3,
                    "embedding": embedding_list
                }
                areas_content.append(item)
        
        area_table = sa.table(
            'areas',
            sa.column('postcode', sa.String),
            sa.column('name', sa.String),
            sa.column('description', sa.String),
            sa.column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024))
        )
        op.bulk_insert(area_table, areas_content)
        
    except Exception as e:
        logger.info(f"Exception type: {type(e).__name__}")
        logger.info(f"Exception Message: {e}")
    


def downgrade() -> None:
    op.execute("DELETE FROM areas")
