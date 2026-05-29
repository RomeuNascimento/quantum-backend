from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.auth.utils import get_usuario_atual
from app.models.models import User, Canal, ProdutoPreco, Produto
from app.schemas.precificacao import (
    CanalCreate, CanalUpdate, CanalOut,
    ProdutoPrecoCreate, ProdutoPrecoUpdate, ProdutoPrecoOut
)
from app.routers.produtos import calcular_produto
from app.routers.receitas import get_valor_hora_padrao

router = APIRouter(prefix="/precificacao", tags=["Precificação"])


def calcular_preco_sugerido(custo_total: float, margem_pct: float, canal: Canal) -> float:
    divisor = 1 - (margem_pct / 100) - (canal.taxa_plataforma_pct / 100) - \
              (canal.taxa_cartao_pct / 100) - (canal.imposto_pct / 100)
    if divisor <= 0:
        return 0.0
    return custo_total / divisor


# ─── CANAIS ──────────────────────────────────────────────────────────────────

@router.get("/canais", response_model=List[CanalOut])
def listar_canais(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    return db.query(Canal).filter(Canal.user_id == user.id, Canal.ativo == True).all()


@router.post("/canais", response_model=CanalOut, status_code=status.HTTP_201_CREATED)
def criar_canal(
    dados: CanalCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    canal = Canal(user_id=user.id, **dados.model_dump())
    db.add(canal)
    db.commit()
    db.refresh(canal)
    return canal


@router.put("/canais/{id}", response_model=CanalOut)
def atualizar_canal(
    id: int,
    dados: CanalUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    canal = db.query(Canal).filter(Canal.id == id, Canal.user_id == user.id).first()
    if not canal:
        raise HTTPException(status_code=404, detail="Canal não encontrado")
    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(canal, campo, valor)
    db.commit()
    db.refresh(canal)
    return canal


@router.delete("/canais/{id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_canal(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    canal = db.query(Canal).filter(Canal.id == id, Canal.user_id == user.id).first()
    if not canal:
        raise HTTPException(status_code=404, detail="Canal não encontrado")
    canal.ativo = False
    db.commit()


# ─── PREÇOS DE PRODUTO ────────────────────────────────────────────────────────

@router.get("/produtos/{produto_id}/precos", response_model=List[ProdutoPrecoOut])
def listar_precos_produto(
    produto_id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = db.query(Produto).filter(
        Produto.id == produto_id, Produto.user_id == user.id
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    vh = get_valor_hora_padrao(user, db)
    calc = calcular_produto(produto, vh)
    custo_total = calc["custo_total"]

    precos = db.query(ProdutoPreco).filter(ProdutoPreco.produto_id == produto_id).all()
    result = []
    for pp in precos:
        if not pp.canal.ativo:
            continue
        sugerido = calcular_preco_sugerido(custo_total, pp.margem_pct, pp.canal)
        result.append(ProdutoPrecoOut(
            id=pp.id,
            produto_id=pp.produto_id,
            canal_id=pp.canal_id,
            canal_nome=pp.canal.nome,
            margem_pct=pp.margem_pct,
            preco_final=pp.preco_final,
            preco_sugerido=sugerido,
            custo_total=custo_total,
        ))
    return result


@router.post("/produtos/{produto_id}/precos", response_model=ProdutoPrecoOut, status_code=status.HTTP_201_CREATED)
def criar_preco_produto(
    produto_id: int,
    dados: ProdutoPrecoCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = db.query(Produto).filter(
        Produto.id == produto_id, Produto.user_id == user.id
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    canal = db.query(Canal).filter(Canal.id == dados.canal_id, Canal.user_id == user.id).first()
    if not canal:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    existente = db.query(ProdutoPreco).filter(
        ProdutoPreco.produto_id == produto_id,
        ProdutoPreco.canal_id == dados.canal_id,
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe precificação para este canal")

    pp = ProdutoPreco(produto_id=produto_id, **dados.model_dump())
    db.add(pp)
    db.commit()
    db.refresh(pp)

    vh = get_valor_hora_padrao(user, db)
    calc = calcular_produto(produto, vh)
    custo_total = calc["custo_total"]
    sugerido = calcular_preco_sugerido(custo_total, pp.margem_pct, canal)

    return ProdutoPrecoOut(
        id=pp.id,
        produto_id=pp.produto_id,
        canal_id=pp.canal_id,
        canal_nome=canal.nome,
        margem_pct=pp.margem_pct,
        preco_final=pp.preco_final,
        preco_sugerido=sugerido,
        custo_total=custo_total,
    )


@router.put("/produtos/{produto_id}/precos/{preco_id}", response_model=ProdutoPrecoOut)
def atualizar_preco_produto(
    produto_id: int,
    preco_id: int,
    dados: ProdutoPrecoUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = db.query(Produto).filter(
        Produto.id == produto_id, Produto.user_id == user.id
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    pp = db.query(ProdutoPreco).filter(
        ProdutoPreco.id == preco_id, ProdutoPreco.produto_id == produto_id
    ).first()
    if not pp:
        raise HTTPException(status_code=404, detail="Precificação não encontrada")

    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(pp, campo, valor)
    db.commit()
    db.refresh(pp)

    vh = get_valor_hora_padrao(user, db)
    calc = calcular_produto(produto, vh)
    custo_total = calc["custo_total"]
    sugerido = calcular_preco_sugerido(custo_total, pp.margem_pct, pp.canal)

    return ProdutoPrecoOut(
        id=pp.id,
        produto_id=pp.produto_id,
        canal_id=pp.canal_id,
        canal_nome=pp.canal.nome,
        margem_pct=pp.margem_pct,
        preco_final=pp.preco_final,
        preco_sugerido=sugerido,
        custo_total=custo_total,
    )


@router.delete("/produtos/{produto_id}/precos/{preco_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_preco_produto(
    produto_id: int,
    preco_id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = db.query(Produto).filter(
        Produto.id == produto_id, Produto.user_id == user.id
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    pp = db.query(ProdutoPreco).filter(
        ProdutoPreco.id == preco_id, ProdutoPreco.produto_id == produto_id
    ).first()
    if not pp:
        raise HTTPException(status_code=404, detail="Precificação não encontrada")
    db.delete(pp)
    db.commit()
