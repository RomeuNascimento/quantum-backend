"""Auditoria dos ingredientes cadastrados em kg/L (bug de unidade M3).

Para um ingrediente em kg/L, `quantidade_embalagem` deve ser o peso da embalagem
NA PRÓPRIA unidade (pacote de 1 kg -> 1, saco de 5 kg -> 5). Se alguém digitou
em GRAMAS (ex.: 1000 para um pacote de 1 kg), o cálculo aplica o fator ×1000 de
novo e o custo sai ~1000× BARATO -> risco de vender no prejuízo.

Este script lista todos os ingredientes ativos em kg/L com o preço mais recente
e sinaliza os suspeitos (quantidade_embalagem alta demais para ser peso em kg/L).

Como rodar (no container backend do EasyPanel, onde DATABASE_URL já está setada):
    python scripts/auditar_unidades.py

Ele só LÊ o banco — não altera nada.
"""
import os
import sys

# Permite rodar de qualquer lugar (adiciona a raiz do repo ao path)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models.models import Ingrediente, IngredientePreco  # noqa: E402

# Acima deste peso, é quase certo que a quantidade foi digitada em gramas/ml
# (poucos ingredientes vêm em embalagem de 100 kg+). Ajuste se você usar sacos
# gigantes (ex.: 50 kg de farinha é legítimo e NÃO deve ser "corrigido").
LIMIAR_SUSPEITO = 100


def unidade_str(u):
    return u.value if hasattr(u, "value") else str(u)


def main():
    db = SessionLocal()
    try:
        ingredientes = (
            db.query(Ingrediente)
            .filter(Ingrediente.ativo == True, Ingrediente.unidade.in_(["kg", "L"]))  # noqa: E712
            .all()
        )
        if not ingredientes:
            print("Nenhum ingrediente ativo em kg/L. Nada a auditar. ✅")
            return

        linhas = []
        for ing in ingredientes:
            preco = (
                db.query(IngredientePreco)
                .filter(IngredientePreco.ingrediente_id == ing.id)
                .order_by(IngredientePreco.data_compra.desc())
                .first()
            )
            if not preco or not preco.quantidade_embalagem:
                linhas.append((ing, None, None, None, "sem preço"))
                continue
            q = float(preco.quantidade_embalagem)
            custo_g = float(preco.preco) / (q * 1000.0)  # o que o app calcula hoje
            suspeito = "⚠️ CONFERIR (parece gramas)" if q >= LIMIAR_SUSPEITO else "ok"
            linhas.append((ing, q, float(preco.preco), custo_g, suspeito))

        linhas.sort(key=lambda x: (x[1] is not None, x[1] or 0), reverse=True)

        print(f"\n{len(ingredientes)} ingrediente(s) ativo(s) em kg/L:\n")
        print(f"{'NOME':<28} {'UN':<3} {'QTD_EMB':>9} {'PREÇO':>9} {'CUSTO/g ou /ml':>16}  SITUAÇÃO")
        print("-" * 90)
        suspeitos = 0
        for ing, q, preco, custo_g, sit in linhas:
            nome = (ing.nome or "")[:28]
            if q is None:
                print(f"{nome:<28} {unidade_str(ing.unidade):<3} {'—':>9} {'—':>9} {'—':>16}  {sit}")
                continue
            if "CONFERIR" in sit:
                suspeitos += 1
            print(f"{nome:<28} {unidade_str(ing.unidade):<3} {q:>9.2f} {preco:>9.2f} {custo_g:>16.6f}  {sit}")

        print("-" * 90)
        if suspeitos:
            print(
                f"\n⚠️  {suspeitos} ingrediente(s) suspeito(s): a quantidade parece estar em "
                "GRAMAS/ML em vez de kg/L.\n"
                "   Correção: editar o ingrediente e pôr a quantidade NA UNIDADE (pacote de 1 kg = 1, "
                "não 1000).\n"
                "   Enquanto não corrigir, o custo desses itens (e o preço sugerido) está ~1000× baixo."
            )
        else:
            print("\nNenhum suspeito pelo limiar. Confira mesmo assim os poucos itens acima. ✅")
    finally:
        db.close()


if __name__ == "__main__":
    main()
