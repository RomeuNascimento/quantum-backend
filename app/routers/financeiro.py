from calendar import monthrange
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.utils import get_usuario_atual
from app.database import get_db
from app.models.models import Lancamento, User
from app.schemas.financeiro import (
    ORIGENS_VALIDAS,
    LancamentoCreate,
    LancamentoOut,
    ResumoFinanceiro,
)

router = APIRouter(prefix="/financeiro", tags=["Financeiro"])


def _intervalo_mes(mes: Optional[str]) -> tuple[date, date, str]:
    """'YYYY-MM' → (primeiro dia, último dia, rótulo). Sem `mes`, usa o atual."""
    if mes:
        try:
            ano, m = mes.split("-")
            ano, m = int(ano), int(m)
            if not (1 <= m <= 12 and 2000 <= ano <= 2100):
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=422, detail="Mês inválido. Use o formato YYYY-MM.")
    else:
        hoje = date.today()
        ano, m = hoje.year, hoje.month
    inicio = date(ano, m, 1)
    fim = date(ano, m, monthrange(ano, m)[1])
    return inicio, fim, f"{ano:04d}-{m:02d}"


@router.get("/lancamentos", response_model=List[LancamentoOut])
def listar(
    mes: Optional[str] = Query(default=None, description="YYYY-MM (default: mês atual)"),
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    inicio, fim, _ = _intervalo_mes(mes)
    return (
        db.query(Lancamento)
        .filter(
            Lancamento.user_id == user.id,
            Lancamento.data >= inicio,
            Lancamento.data <= fim,
        )
        .order_by(Lancamento.data.desc(), Lancamento.id.desc())
        .all()
    )


@router.post("/lancamentos", response_model=LancamentoOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: LancamentoCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    origem = dados.origem if dados.origem in ORIGENS_VALIDAS else "manual"
    lanc = Lancamento(
        user_id=user.id,
        tipo=dados.tipo,
        valor=dados.valor,
        descricao=(dados.descricao or None),
        categoria=(dados.categoria or None),
        data=dados.data or date.today(),
        origem=origem,
    )
    db.add(lanc)
    db.commit()
    db.refresh(lanc)
    return lanc


@router.delete("/lancamentos/{id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    lanc = (
        db.query(Lancamento)
        .filter(Lancamento.id == id, Lancamento.user_id == user.id)
        .first()
    )
    if not lanc:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    db.delete(lanc)
    db.commit()


@router.get("/resumo", response_model=ResumoFinanceiro)
def resumo(
    mes: Optional[str] = Query(default=None, description="YYYY-MM (default: mês atual)"),
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    inicio, fim, rotulo = _intervalo_mes(mes)
    lancs = (
        db.query(Lancamento)
        .filter(
            Lancamento.user_id == user.id,
            Lancamento.data >= inicio,
            Lancamento.data <= fim,
        )
        .all()
    )
    entradas = sum(l.valor for l in lancs if l.tipo == "entrada")
    saidas = sum(l.valor for l in lancs if l.tipo == "saida")
    por_categoria: dict[str, float] = {}
    for l in lancs:
        if l.tipo == "saida":
            cat = l.categoria or "outros"
            por_categoria[cat] = por_categoria.get(cat, 0.0) + l.valor
    return ResumoFinanceiro(
        mes=rotulo,
        entradas=entradas,
        saidas=saidas,
        sobra=entradas - saidas,
        quantidade=len(lancs),
        saidas_por_categoria=[
            {"categoria": c, "total": t}
            for c, t in sorted(por_categoria.items(), key=lambda kv: -kv[1])
        ],
    )
