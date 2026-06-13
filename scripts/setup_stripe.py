"""Setup único do Stripe: produto + preço anual + webhook.

Rodar UMA vez, de uma máquina com acesso a api.stripe.com:

    pip install stripe
    STRIPE_API_KEY=rk_live_... python scripts/setup_stripe.py

Imprime STRIPE_PRICE_ID e STRIPE_WEBHOOK_SECRET para configurar no EasyPanel.
Idempotente: reaproveita produto/preço/webhook se já existirem.
"""
import os
import sys

import stripe

stripe.api_key = os.environ["STRIPE_API_KEY"]

PRODUTO_NOME = "Quantum — Plano Anual"
VALOR_CENTAVOS = 14700  # R$ 147,00
VALOR_MENSAL_CENTAVOS = 1990  # R$ 19,90/mês (anual sai ~38% mais barato)
WEBHOOK_URL = "https://api.quantumcalc.com.br/billing/webhook"
WEBHOOK_EVENTOS = [
    "checkout.session.completed",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.subscription.deleted",
]


def main() -> None:
    # Produto
    produto = next((p for p in stripe.Product.list(limit=100).auto_paging_iter()
                    if p.name == PRODUTO_NOME and p.active), None)
    if produto is None:
        produto = stripe.Product.create(name=PRODUTO_NOME)
        print(f"Produto criado: {produto.id}")
    else:
        print(f"Produto existente: {produto.id}")

    # Preço anual R$147
    preco = next((pr for pr in stripe.Price.list(product=produto.id, active=True, limit=100)
                  if pr.unit_amount == VALOR_CENTAVOS and pr.currency == "brl"
                  and pr.recurring and pr.recurring.interval == "year"), None)
    if preco is None:
        preco = stripe.Price.create(
            product=produto.id,
            unit_amount=VALOR_CENTAVOS,
            currency="brl",
            recurring={"interval": "year"},
        )
        print(f"Preço criado: {preco.id}")
    else:
        print(f"Preço existente: {preco.id}")

    # Preço mensal R$19,90 (mesmo produto)
    preco_mensal = next((pr for pr in stripe.Price.list(product=produto.id, active=True, limit=100)
                         if pr.unit_amount == VALOR_MENSAL_CENTAVOS and pr.currency == "brl"
                         and pr.recurring and pr.recurring.interval == "month"), None)
    if preco_mensal is None:
        preco_mensal = stripe.Price.create(
            product=produto.id,
            unit_amount=VALOR_MENSAL_CENTAVOS,
            currency="brl",
            recurring={"interval": "month"},
        )
        print(f"Preço mensal criado: {preco_mensal.id}")
    else:
        print(f"Preço mensal existente: {preco_mensal.id}")

    # Webhook
    wh = next((w for w in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter()
               if w.url == WEBHOOK_URL), None)
    if wh is None:
        wh = stripe.WebhookEndpoint.create(url=WEBHOOK_URL, enabled_events=WEBHOOK_EVENTOS)
        print(f"Webhook criado: {wh.id}")
        print(f"\n⚠️  GUARDE — o secret só aparece agora:\nSTRIPE_WEBHOOK_SECRET={wh.secret}")
    else:
        print(f"Webhook existente: {wh.id} (secret não é re-exibido; veja no painel ou delete e rode de novo)")

    print(f"\nConfigurar no EasyPanel (serviço backend):")
    print(f"STRIPE_API_KEY=<a chave rk_live usada agora>")
    print(f"STRIPE_PRICE_ID={preco.id}")
    print(f"STRIPE_PRICE_ID_MENSAL={preco_mensal.id}")


if __name__ == "__main__":
    try:
        main()
    except stripe.error.PermissionError as e:
        sys.exit(f"Permissão faltando na chave restrita: {e}")
