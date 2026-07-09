"""Produto: adiciona coluna foto (data URL base64, opcional)

Revision ID: 009
Revises: 008
Create Date: 2026-07-09

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("produtos", sa.Column("foto", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("produtos", "foto")
