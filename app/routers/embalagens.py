from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.auth.utils import get_usuario_atual
from app.models.models import User, Embalagem, EmbalagemPreco, ProdutoEmbalagem
from app.schemas.embalagens import (
    EmbalagemCreate, EmbalagemUpdate, EmbalagemOut,
    EmbalagemDetalhe, EmbalagemPrecoCreate, EmbalagemPrecoOut
)

router = APIRouter(prefix="/embalagens", tags=["Embalagens"])


def calcular_custo_unitario(preco: EmbalagemPreco) -> float:
    if preco is None or preco.quantidade_embalagem == 0:
        return 0.0
    return preco.preco / preco.quantidade_embalagem


@router.get("/", response_model=List[EmbalagemOut])
def listar(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    embalagens = db.query(Embalagem).filter(
        Embalagem.user_id == user.id, Embalagem.ativo == True
    ).all()
    result = []
    for emb in embalagens:
        ultimo = next(
            (p for p in sorted(emb.precos, key=lambda x: x.data_compra, reverse=True)),
            None
        )
        custo = calcular_custo_unitario(ultimo) if ultimo else None
        out = EmbalagemOut.model_validate(emb)
        out.custo_unitario_atual = custo
        result.append(out)
    return result


@router.post("/", response_model=EmbalagemOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: EmbalagemCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    emb = Embalagem(user_id=user.id, nome=dados.nome, unidade=dados.unidade)
    db.add(emb)
    db.flush()

    custo = None
    if dados.preco_inicial:
        preco = EmbalagemPreco(
            embalagem_id=emb.id,
            preco=dados.preco_inicial.preco,
            quantidade_embalagem=dados.preco_inicial.quantidade_embalagem,
            data_compra=dados.preco_inicial.data_compra,
            origem=dados.preco_inicial.origem,
            observacao=dados.preco_inicial.observacao,
        )
        db.add(preco)
        db.flush()
        custo = calcular_custo_unitario(preco)

    db.commit()
    db.refresh(emb)
    out = EmbalagemOut.model_validate(emb)
    out.custo_unitario_atual = custo
    return out


@router.get("/{id}", response_model=EmbalagemDetalhe)
def detalhar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    emb = db.query(Embalagem).filter(
        Embalagem.id == id, Embalagem.user_id == user.id
    ).first()
    if not emb:
        raise HTTPException(status_code=404, detail="Embalagem não encontrada")

    precos_ordenados = sorted(emb.precos, key=lambda x: x.data_compra, reverse=True)
    ultimo = precos_ordenados[0] if precos_ordenados else None
    custo_atual = calcular_custo_unitario(ultimo) if ultimo else None

    precos_out = []
    for p in precos_ordenados:
        po = EmbalagemPrecoOut.model_validate(p)
        po.custo_unitario = calcular_custo_unitario(p)
        precos_out.append(po)

    out = EmbalagemDetalhe.model_validate(emb)
    out.custo_unitario_atual = custo_atual
    out.historico_precos = precos_out
    return out


@router.put("/{id}", response_model=EmbalagemOut)
def atualizar(
    id: int,
    dados: EmbalagemUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    emb = db.query(Embalagem).filter(
        Embalagem.id == id, Embalagem.user_id == user.id
    ).first()
    if not emb:
        raise HTTPException(status_code=404, detail="Embalagem não encontrada")

    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(emb, campo, valor)

    db.commit()
    db.refresh(emb)
    precos = sorted(emb.precos, key=lambda x: x.data_compra, reverse=True)
    custo = calcular_custo_unitario(precos[0]) if precos else None
    out = EmbalagemOut.model_validate(emb)
    out.custo_unitario_atual = custo
    return out


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    emb = db.query(Embalagem).filter(
        Embalagem.id == id, Embalagem.user_id == user.id
    ).first()
    if not emb:
        raise HTTPException(status_code=404, detail="Embalagem não encontrada")

    em_uso = db.query(ProdutoEmbalagem).filter(ProdutoEmbalagem.embalagem_id == id).first()
    if em_uso:
        emb.ativo = False
        db.commit()
    else:
        db.delete(emb)
        db.commit()


@router.post("/{id}/precos", response_model=EmbalagemPrecoOut, status_code=status.HTTP_201_CREATED)
def adicionar_preco(
    id: int,
    dados: EmbalagemPrecoCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    emb = db.query(Embalagem).filter(
        Embalagem.id == id, Embalagem.user_id == user.id
    ).first()
    if not emb:
        raise HTTPException(status_code=404, detail="Embalagem não encontrada")

    preco = EmbalagemPreco(
        embalagem_id=id,
        preco=dados.preco,
        quantidade_embalagem=dados.quantidade_embalagem,
        data_compra=dados.data_compra,
        origem=dados.origem,
        observacao=dados.observacao,
    )
    db.add(preco)
    db.commit()
    db.refresh(preco)
    out = EmbalagemPrecoOut.model_validate(preco)
    out.custo_unitario = calcular_custo_unitario(preco)
    return out
