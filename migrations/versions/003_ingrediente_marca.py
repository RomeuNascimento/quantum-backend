"""Ingrediente: adiciona coluna marca

Revision ID: 003
Revises: 002
Create Date: 2026-05-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ingredientes", sa.Column("marca", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("ingredientes", "marca")
