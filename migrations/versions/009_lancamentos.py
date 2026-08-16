"""Financeiro: tabela lancamentos (fluxo de caixa entrou/saiu).

Base do assistente financeiro — lançamentos manuais, interpretados por IA
(texto/comprovante Pix), derivados de nota fiscal e, na fase 2, via WhatsApp.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("valor", sa.Numeric(12, 4), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=True),
        sa.Column("categoria", sa.String(50), nullable=True),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("origem", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_lancamentos_user_id", "lancamentos", ["user_id"])
    op.create_index("ix_lancamentos_data", "lancamentos", ["data"])


def downgrade() -> None:
    op.drop_index("ix_lancamentos_data", table_name="lancamentos")
    op.drop_index("ix_lancamentos_user_id", table_name="lancamentos")
    op.drop_table("lancamentos")
