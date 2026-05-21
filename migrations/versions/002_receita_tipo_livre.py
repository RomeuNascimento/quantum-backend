"""Receita.tipo: enum → varchar livre

Revision ID: 002
Revises: 001
Create Date: 2026-05-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Converte a coluna de ENUM nativo para VARCHAR,
    # preservando os valores existentes ("massa", "recheio") como texto.
    op.execute(
        "ALTER TABLE receitas ALTER COLUMN tipo TYPE VARCHAR(100) USING tipo::text"
    )
    op.alter_column("receitas", "tipo", nullable=True)
    op.execute("DROP TYPE IF EXISTS tiporeceitaenum")


def downgrade() -> None:
    # Recria o enum e reverte — valores fora de {'massa','recheio'} voltam como 'massa'.
    op.execute("CREATE TYPE tiporeceitaenum AS ENUM ('massa', 'recheio')")
    op.execute(
        """
        UPDATE receitas
        SET tipo = 'massa'
        WHERE tipo IS NULL OR tipo NOT IN ('massa', 'recheio')
        """
    )
    op.execute(
        "ALTER TABLE receitas ALTER COLUMN tipo TYPE tiporeceitaenum USING tipo::tiporeceitaenum"
    )
    op.alter_column("receitas", "tipo", nullable=False)
