"""Tabela stripe_events — idempotência do webhook do Stripe.

O Stripe entrega eventos at-least-once (reenvia em caso de retry/timeout).
Sem registro do event_id já processado, o mesmo evento pode ser reprocessado
e gerar validades de assinatura divergentes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripe_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("recebido_em", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_stripe_events_event_id", "stripe_events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_stripe_events_event_id", table_name="stripe_events")
    op.drop_table("stripe_events")
