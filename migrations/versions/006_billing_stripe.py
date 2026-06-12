"""Billing Stripe: colunas de assinatura em users.

Contas existentes ficam com assinatura_status='ativa' e validade NULL
(ativa sem expiração) — ninguém em produção é bloqueado pelo lançamento
do paywall. Contas novas nascem com o default 'trial' (7 dias).

Revision ID: 006
Revises: 005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(100), nullable=True))
    op.create_index("ix_users_stripe_customer_id", "users", ["stripe_customer_id"])
    op.add_column(
        "users",
        sa.Column("assinatura_status", sa.String(20), nullable=False, server_default="trial"),
    )
    op.add_column("users", sa.Column("assinatura_validade", sa.DateTime(), nullable=True))
    # Contas pré-existentes: ativas sem expiração
    op.execute("UPDATE users SET assinatura_status = 'ativa'")


def downgrade() -> None:
    op.drop_column("users", "assinatura_validade")
    op.drop_column("users", "assinatura_status")
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "stripe_customer_id")
