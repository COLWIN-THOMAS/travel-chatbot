"""add trips.start_date

Revision ID: a41c9d2e7b10
Revises: 938f480f88ec
Create Date: 2026-10-08 13:30:00.000000

Existing trips keep start_date NULL ("undated"); the app treats them exactly as before.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a41c9d2e7b10'
down_revision: Union[str, Sequence[str], None] = '938f480f88ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trips', sa.Column('start_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('trips', 'start_date')
