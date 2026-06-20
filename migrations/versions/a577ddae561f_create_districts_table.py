"""create districts table

Revision ID: a577ddae561f
Revises: f8ce44dc39eb
Create Date: 2026-04-29 11:01:11.210945

"""
import logging

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = 'a577ddae561f'
down_revision: Union[str, Sequence[str], None] = 'f8ce44dc39eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely."""
    # Inspect the current database state
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()
    
    # Only create if the table does not exist yet
    if 'districts' not in existing_tables:
        op.create_table(
            'districts',
            sa.Column('postcode', sa.String(length=6), nullable=False),
            sa.Column('category', sa.String(length=1), nullable=False),  # General, Flats, Houses, Detached, Semi-Detached, Terraced
            sa.Column('parent', sa.String(length=2), nullable=False),
            sa.Column('post_town', sa.String(length=50), nullable=True),
            sa.Column('avg_price', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['parent'], ['areas.postcode'], name='fk_districts_parent_areas'),
            sa.PrimaryKeyConstraint('postcode', 'category', name='districts_pkey')
        )
        op.create_index(
            'idx_districts_parent_category',
            'districts',
            ['parent', 'category']
        )
    else:
        existing_fks = inspector.get_foreign_keys('districts')
        fk_exists = any(fk['name'] == 'fk_districts_parent_areas' for fk in existing_fks)
        if not fk_exists:
            logger.info("Foreign key 'fk_districts_parent_areas' not found. Creating it...")
            op.create_foreign_key(
                constraint_name='fk_districts_parent_areas',
                source_table='districts',
                referent_table='areas',
                local_cols=['parent'],
                remote_cols=['postcode']
            )
        
        existing_indexes = inspector.get_indexes('districts')
        idx_exists = any(idx['name'] == 'idx_districts_parent_category' for idx in existing_indexes)
        if not idx_exists:
            logger.info("Index 'idx_districts_parent_category' not found. Creating it...")
            op.create_index(
                'idx_districts_parent_category',
                'districts',
                ['parent', 'category']
            )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema safely."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()
    
    # Only drop if the table actually exists
    if 'districts' in existing_tables:
        op.drop_table('districts')
    # ### end Alembic commands ###
