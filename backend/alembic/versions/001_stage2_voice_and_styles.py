"""Stage 2: Add detected_language, translation_style, and input_method to translations table

Revision ID: 001_stage2
Revises: 
Create Date: 2026-09-23
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_stage2'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use batch alter for SQLite compatibility if needed
    with op.batch_alter_table('translations') as batch_op:
        batch_op.add_column(sa.Column('detected_language', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('translation_style', sa.String(length=32), server_default='general', nullable=False))
        batch_op.add_column(sa.Column('input_method', sa.String(length=16), server_default='text', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('translations') as batch_op:
        batch_op.drop_column('input_method')
        batch_op.drop_column('translation_style')
        batch_op.drop_column('detected_language')
