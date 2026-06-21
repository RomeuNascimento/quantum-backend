"""Compara a extração da IA (receita ou nota) entre Haiku / Sonnet / Opus.

Roda a MESMA imagem nos 3 modelos e imprime o JSON extraído + tokens + custo
real de cada um, pra decidir com dado se dá pra baixar de Opus → Sonnet/Haiku.

Uso:
    ANTHROPIC_API_KEY=sk-... python scripts/comparar_modelos_ia.py caminho/da/foto.jpg --tipo receita
    ANTHROPIC_API_KEY=sk-... python scripts/comparar_modelos_ia.py caminho/da/nota.jpg --tipo nota

Não toca em produção — é só leitura/medição.
"""
import argparse
import json
import sys
import time

import anthropic

from app.routers.ia import (
    PROMPT_NOTA, PROMPT_RECEITAS, BLOCO_SEGURANCA, _image_block, _parse,
)

# Preços por milhão de tokens (input, output) — atualizar se mudar
PRECOS = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
}
USD_BRL = 5.5  # aproximado, só pra referência


def custo(modelo, usage):
    pin, pout = PRECOS[modelo]
    usd = usage.input_tokens / 1e6 * pin + usage.output_tokens / 1e6 * pout
    return usd, usd * USD_BRL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imagem", help="caminho da foto (jpg/png/pdf)")
    ap.add_argument("--tipo", choices=["receita", "nota"], default="receita")
    args = ap.parse_args()

    with open(args.imagem, "rb") as f:
        content = f.read()
    block = _image_block(content)
    prompt = (PROMPT_NOTA if args.tipo == "nota" else PROMPT_RECEITAS) + BLOCO_SEGURANCA
    chave = "itens" if args.tipo == "nota" else "receitas"

    client = anthropic.Anthropic()
    for modelo in PRECOS:
        print("\n" + "=" * 70)
        print(f"MODELO: {modelo}")
        print("=" * 70)
        t0 = time.time()
        try:
            resp = client.messages.create(
                model=modelo, max_tokens=4096,
                messages=[{"role": "user", "content": [block, {"type": "text", "text": prompt}]}],
            )
            dt = time.time() - t0
            usd, brl = custo(modelo, resp.usage)
            try:
                data = _parse(resp, chave)
                print(json.dumps(data, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"⚠️  parse falhou: {e}\nbruto: {resp.content[0].text[:500]}")
            print(f"\n  tokens: {resp.usage.input_tokens} in / {resp.usage.output_tokens} out")
            print(f"  tempo:  {dt:.1f}s")
            print(f"  custo:  US$ {usd:.4f}  ≈  R$ {brl:.3f}")
        except anthropic.APIError as e:
            print(f"ERRO: {e}")


if __name__ == "__main__":
    main()
