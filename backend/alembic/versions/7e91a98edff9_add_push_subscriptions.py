"""add push subscriptions

Build Plan 3, Unit 23. Purely additive: one new table, no enum, no change to
any existing table.

Revision ID: 7e91a98edff9
Revises: 8fcad7e710dc
Create Date: 2026-09-24 23:53:01.498052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7e91a98edff9'
down_revision: Union[str, Sequence[str], None] = '8fcad7e710dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('push_subscriptions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('endpoint', sa.Text(), nullable=False),
    sa.Column('p256dh', sa.Text(), nullable=False),
    sa.Column('auth', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('endpoint')
    )


def downgrade() -> None:
    op.drop_table('push_subscriptions')
