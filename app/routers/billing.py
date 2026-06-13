"""Billing — assinatura anual via Stripe.

Env vars (EasyPanel, serviço backend):
  STRIPE_API_KEY        — chave restrita (rk_live_...)
  STRIPE_PRICE_ID       — price do plano anual (criado por scripts/setup_stripe.py)
  STRIPE_WEBHOOK_SECRET — signing secret do webhook (whsec_...)
  FRONTEND_URL          — default https://quantumcalc.com.br

Sem STRIPE_API_KEY os endpoints retornam 503 (mesmo padrão da IA).
O webhook é a única fonte de verdade do status: o checkout redireciona o
usuário de volta, mas é o evento do Stripe que ativa a assinatura.
"""
import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.utils import get_usuario_atual
from app.database import get_db
from app.models.models import StripeEvent, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["Billing"])

TRIAL_DIAS = 7


def _stripe():
    try:
        import stripe
    except ImportError:
        raise HTTPException(status_code=503, detail="Biblioteca stripe não instalada no servidor.")
    key = os.getenv("STRIPE_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="Pagamentos não configurados no servidor.")
    stripe.api_key = key
    return stripe


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "https://quantumcalc.com.br").rstrip("/")


def _trial_fim(user: User) -> datetime:
    return (user.criado_em or datetime.utcnow()) + timedelta(days=TRIAL_DIAS)


def status_efetivo(user: User) -> str:
    """'trial' | 'ativa' | 'vencida' considerando expirações."""
    if user.assinatura_status == "ativa":
        # validade None = ativa sem expiração (contas legadas/cortesia)
        if user.assinatura_validade and user.assinatura_validade < datetime.utcnow():
            return "vencida"
        return "ativa"
    if user.assinatura_status == "trial":
        return "trial" if _trial_fim(user) > datetime.utcnow() else "vencida"
    return "vencida"


@router.get("/status")
def billing_status(user: User = Depends(get_usuario_atual)):
    return {
        "status": status_efetivo(user),
        "trial_fim": _trial_fim(user).isoformat() if user.assinatura_status == "trial" else None,
        "validade": user.assinatura_validade.isoformat() if user.assinatura_validade else None,
    }


def _customer_id(stripe, user: User, db: Session) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email, name=user.nome, metadata={"user_id": str(user.id)}
    )
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


# Endpoints síncronos (def) de propósito: chamadas à API do Stripe rodam no
# threadpool e não travam o event loop (mesma decisão dos endpoints /ia/).
@router.post("/checkout")
def criar_checkout(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    stripe = _stripe()
    price_id = os.getenv("STRIPE_PRICE_ID")
    if not price_id:
        raise HTTPException(status_code=503, detail="Plano não configurado no servidor.")
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=_customer_id(stripe, user, db),
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{_frontend_url()}/assinatura?sucesso=1",
        cancel_url=f"{_frontend_url()}/assinatura",
        client_reference_id=str(user.id),
    )
    return {"url": session.url}


@router.post("/portal")
def portal_cliente(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    stripe = _stripe()
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Nenhuma assinatura encontrada para esta conta.")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{_frontend_url()}/assinatura",
    )
    return {"url": session.url}


def _user_por_customer(db: Session, customer_id: str) -> User | None:
    return db.query(User).filter(User.stripe_customer_id == customer_id).first()


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    stripe = _stripe()
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook não configurado.")
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Assinatura do webhook inválida.")

    tipo = event["type"]
    obj = event["data"]["object"]

    # Idempotência: o Stripe entrega at-least-once e reenvia eventos. O registro
    # do event_id (UNIQUE) garante que reprocessos viram no-op.
    if db.query(StripeEvent).filter(StripeEvent.event_id == event["id"]).first():
        return {"received": True}
    db.add(StripeEvent(event_id=event["id"], tipo=tipo))

    if tipo in ("checkout.session.completed", "invoice.paid"):
        user = _user_por_customer(db, obj.get("customer"))
        if user:
            user.assinatura_status = "ativa"
            # validade = fim do período pago + 3 dias de carência p/ retry de cobrança
            period_end = None
            if tipo == "invoice.paid":
                linhas = obj.get("lines", {}).get("data", [])
                if linhas:
                    period_end = linhas[0].get("period", {}).get("end")
            if period_end:
                user.assinatura_validade = datetime.utcfromtimestamp(period_end) + timedelta(days=3)
            else:
                user.assinatura_validade = datetime.utcnow() + timedelta(days=368)
            logger.info("billing: assinatura ativa user_id=%s (%s)", user.id, tipo)
    elif tipo in ("customer.subscription.deleted", "invoice.payment_failed"):
        user = _user_por_customer(db, obj.get("customer"))
        if user and tipo == "customer.subscription.deleted":
            user.assinatura_status = "vencida"
            logger.info("billing: assinatura encerrada user_id=%s", user.id)
        # payment_failed: não derruba na hora — a validade (com carência) expira sozinha

    try:
        db.commit()
    except IntegrityError:
        # Entrega concorrente do mesmo evento: a UNIQUE segurou o duplicado
        db.rollback()
    return {"received": True}


def require_assinatura_ativa(user: User = Depends(get_usuario_atual)) -> User:
    """Dependency: bloqueia rotas de negócio se a assinatura estiver vencida."""
    if status_efetivo(user) == "vencida":
        raise HTTPException(
            status_code=402,
            detail="Assinatura vencida. Acesse /assinatura para renovar.",
        )
    return user
