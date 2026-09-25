"""add goal relations

Unit 25. Purely additive: one new table recording which goals Chris says are
related. No existing table changes.

Revision ID: b016cac9046d
Revises: 7e91a98edff9
Create Date: 2026-09-25 02:48:16.971346

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b016cac9046d'
down_revision: Union[str, Sequence[str], None] = '7e91a98edff9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('goal_relations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('goal_a_id', sa.UUID(), nullable=False),
    sa.Column('goal_b_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('goal_a_id < goal_b_id', name='ck_goal_relations_ordered'),
    sa.ForeignKeyConstraint(['goal_a_id'], ['goals.id'], ),
    sa.ForeignKeyConstraint(['goal_b_id'], ['goals.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('goal_a_id', 'goal_b_id', name='uq_goal_relations_pair')
    )
    op.create_index(op.f('ix_goal_relations_goal_a_id'), 'goal_relations', ['goal_a_id'], unique=False)
    op.create_index(op.f('ix_goal_relations_goal_b_id'), 'goal_relations', ['goal_b_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_goal_relations_goal_b_id'), table_name='goal_relations')
    op.drop_index(op.f('ix_goal_relations_goal_a_id'), table_name='goal_relations')
    op.drop_table('goal_relations')
