from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc
from typing import List
from datetime import datetime
from app.routers.unidades import fator_unidade
from app.database import get_db
from app.auth.utils import get_usuario_atual
from app.models.models import User, Ingrediente, IngredientePreco, ReceitaIngrediente, ProdutoIngrediente
from app.schemas.ingredientes import (
    IngredienteCreate, IngredienteUpdate, IngredienteOut,
    IngredienteDetalhe, IngredientePrecoCreate, IngredientePrecoOut
)

router = APIRouter(prefix="/ingredientes", tags=["Ingredientes"])


def calcular_custo_unitario(preco: IngredientePreco, fator_correcao: float, unidade=None) -> float:
    if preco is None or preco.quantidade_embalagem == 0 or fator_correcao == 0:
        return 0.0
    base = preco.quantidade_embalagem * fator_unidade(unidade)
    return (preco.preco / base) / fator_correcao


def preco_mais_recente(ingrediente: Ingrediente) -> IngredientePreco | None:
    return (
        db_preco
        for db_preco in sorted(ingrediente.precos, key=lambda p: p.data_compra, reverse=True)
    ).__next__() if ingrediente.precos else None


@router.get("/", response_model=List[IngredienteOut])
def listar(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    ingredientes = db.query(Ingrediente).options(
        selectinload(Ingrediente.precos)
    ).filter(
        Ingrediente.user_id == user.id, Ingrediente.ativo == True
    ).all()
    result = []
    for ing in ingredientes:
        ultimo = next(
            (p for p in sorted(ing.precos, key=lambda x: x.data_compra, reverse=True)),
            None
        )
        custo = calcular_custo_unitario(ultimo, ing.fator_correcao, ing.unidade) if ultimo else None
        out = IngredienteOut.model_validate(ing)
        out.custo_unitario_atual = custo
        result.append(out)
    return result


@router.post("/", response_model=IngredienteOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: IngredienteCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    ing = Ingrediente(
        user_id=user.id,
        nome=dados.nome,
        marca=dados.marca,
        unidade=dados.unidade,
        fator_correcao=dados.fator_correcao,
    )
    db.add(ing)
    db.flush()

    custo = None
    if dados.preco_inicial:
        preco = IngredientePreco(
            ingrediente_id=ing.id,
            preco=dados.preco_inicial.preco,
            quantidade_embalagem=dados.preco_inicial.quantidade_embalagem,
            data_compra=dados.preco_inicial.data_compra,
            origem=dados.preco_inicial.origem,
            observacao=dados.preco_inicial.observacao,
        )
        db.add(preco)
        db.flush()
        custo = calcular_custo_unitario(preco, ing.fator_correcao, ing.unidade)

    db.commit()
    db.refresh(ing)
    out = IngredienteOut.model_validate(ing)
    out.custo_unitario_atual = custo
    return out


@router.get("/{id}", response_model=IngredienteDetalhe)
def detalhar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).filter(
        Ingrediente.id == id, Ingrediente.user_id == user.id
    ).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente não encontrado")

    precos_ordenados = sorted(ing.precos, key=lambda x: x.data_compra, reverse=True)
    ultimo = precos_ordenados[0] if precos_ordenados else None
    custo_atual = calcular_custo_unitario(ultimo, ing.fator_correcao, ing.unidade) if ultimo else None

    precos_out = []
    for p in precos_ordenados:
        po = IngredientePrecoOut.model_validate(p)
        po.custo_unitario = calcular_custo_unitario(p, ing.fator_correcao, ing.unidade)
        precos_out.append(po)

    out = IngredienteDetalhe.model_validate(ing)
    out.custo_unitario_atual = custo_atual
    out.historico_precos = precos_out
    return out


@router.put("/{id}", response_model=IngredienteOut)
def atualizar(
    id: int,
    dados: IngredienteUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).filter(
        Ingrediente.id == id, Ingrediente.user_id == user.id
    ).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente não encontrado")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(ing, campo, valor)

    db.commit()
    db.refresh(ing)
    precos = sorted(ing.precos, key=lambda x: x.data_compra, reverse=True)
    custo = calcular_custo_unitario(precos[0], ing.fator_correcao, ing.unidade) if precos else None
    out = IngredienteOut.model_validate(ing)
    out.custo_unitario_atual = custo
    return out


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).filter(
        Ingrediente.id == id, Ingrediente.user_id == user.id
    ).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente não encontrado")

    em_uso = (
        db.query(ReceitaIngrediente).filter(ReceitaIngrediente.ingrediente_id == id).first()
        or db.query(ProdutoIngrediente).filter(ProdutoIngrediente.ingrediente_id == id).first()
    )
    if em_uso:
        ing.ativo = False
        db.commit()
    else:
        db.delete(ing)
        db.commit()


@router.post("/{id}/precos", response_model=IngredientePrecoOut, status_code=status.HTTP_201_CREATED)
def adicionar_preco(
    id: int,
    dados: IngredientePrecoCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).filter(
        Ingrediente.id == id, Ingrediente.user_id == user.id
    ).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente não encontrado")

    preco = IngredientePreco(
        ingrediente_id=id,
        preco=dados.preco,
        quantidade_embalagem=dados.quantidade_embalagem,
        data_compra=dados.data_compra,
        origem=dados.origem,
        observacao=dados.observacao,
    )
    db.add(preco)
    db.commit()
    db.refresh(preco)
    out = IngredientePrecoOut.model_validate(preco)
    out.custo_unitario = calcular_custo_unitario(preco, ing.fator_correcao, ing.unidade)
    return out
