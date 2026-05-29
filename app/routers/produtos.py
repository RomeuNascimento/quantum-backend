from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.auth.utils import get_usuario_atual
from app.models.models import (
    User, Produto, ProdutoMassa, ProdutoRecheio, ProdutoIngrediente,
    ProdutoEmbalagem, ProdutoMOMontagem, Receita, Ingrediente, Embalagem, Colaborador
)
from app.schemas.produtos import (
    ProdutoCreate, ProdutoUpdate, ProdutoOut, ProdutoDetalhe,
    PrepOut, IngAvulsoOut, EmbOut, ProdutoMOMontagemOut, ProdutoPreparacaoCreate
)
from app.routers.receitas import calcular_receita, get_valor_hora_padrao, custo_unitario_ingrediente

router = APIRouter(prefix="/produtos", tags=["Produtos"])


def custo_unitario_embalagem(embalagem: Embalagem) -> float:
    precos = sorted(embalagem.precos, key=lambda p: p.data_compra, reverse=True)
    if not precos:
        return 0.0
    p = precos[0]
    return p.preco / p.quantidade_embalagem if p.quantidade_embalagem > 0 else 0.0


def calcular_produto(produto: Produto, valor_hora_padrao: float) -> dict:
    custo_mp = 0.0
    custo_mo = 0.0
    custo_emb = 0.0

    preparacoes_out = []
    for pm in list(produto.massas) + list(produto.recheios):
        receita = pm.receita
        if not receita:
            continue
        calc = calcular_receita(receita, valor_hora_padrao)
        fator = pm.quantidade_g / receita.rendimento_g if receita.rendimento_g > 0 else 0.0
        custo_prep = (calc["custo_mp_total"] + calc["custo_mo_total"]) * fator
        custo_mp += calc["custo_mp_total"] * fator
        custo_mo += calc["custo_mo_total"] * fator
        preparacoes_out.append(PrepOut(
            id=pm.id,
            receita_id=pm.receita_id,
            nome=receita.nome,
            quantidade=pm.quantidade_g,
            custo=custo_prep,
        ))

    ingredientes_out = []
    for pi in produto.ingredientes:
        cu = custo_unitario_ingrediente(pi.ingrediente)
        custo = cu * pi.quantidade_g
        custo_mp += custo
        ingredientes_out.append(IngAvulsoOut(
            id=pi.id,
            ingrediente_id=pi.ingrediente_id,
            nome=pi.ingrediente.nome,
            quantidade=pi.quantidade_g,
            custo=custo,
        ))

    embalagens_out = []
    for pe in produto.embalagens:
        cu = custo_unitario_embalagem(pe.embalagem)
        custo = cu * pe.quantidade
        custo_emb += custo
        embalagens_out.append(EmbOut(
            id=pe.id,
            embalagem_id=pe.embalagem_id,
            nome=pe.embalagem.nome,
            quantidade=pe.quantidade,
            custo=custo,
        ))

    mo_out = []
    for mo in produto.mo_montagem:
        if mo.colaborador_id and mo.colaborador:
            vh = mo.colaborador.valor_hora
            nome = mo.colaborador.nome
        else:
            vh = valor_hora_padrao
            nome = None
        custo_mo_item = (vh / 60) * mo.tempo_min
        custo_mo += custo_mo_item
        mo_out.append(ProdutoMOMontagemOut(
            id=mo.id,
            descricao=mo.descricao,
            tempo_min=mo.tempo_min,
            colaborador_nome=nome,
            custo=custo_mo_item,
        ))

    custo_total = custo_mp + custo_mo + custo_emb

    return {
        "preparacoes": preparacoes_out,
        "ingredientes_avulsos": ingredientes_out,
        "embalagens": embalagens_out,
        "mo_montagem": mo_out,
        "custo_mp_total": custo_mp,
        "custo_mo_total": custo_mo,
        "custo_embalagens_total": custo_emb,
        "custo_total": custo_total,
    }


@router.get("/", response_model=List[ProdutoOut])
def listar(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    return db.query(Produto).filter(
        Produto.user_id == user.id, Produto.ativo == True
    ).all()


@router.post("/", response_model=ProdutoDetalhe, status_code=status.HTTP_201_CREATED)
def criar(
    dados: ProdutoCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = Produto(user_id=user.id, nome=dados.nome)
    db.add(produto)
    db.flush()

    for p in dados.preparacoes:
        db.add(ProdutoMassa(produto_id=produto.id, receita_id=p.receita_id, quantidade_g=p.quantidade_g))
    for i in dados.ingredientes:
        db.add(ProdutoIngrediente(produto_id=produto.id, ingrediente_id=i.ingrediente_id, quantidade_g=i.quantidade_g))
    for e in dados.embalagens:
        db.add(ProdutoEmbalagem(produto_id=produto.id, embalagem_id=e.embalagem_id, quantidade=e.quantidade))
    for mo in dados.mo_montagem:
        db.add(ProdutoMOMontagem(produto_id=produto.id, descricao=mo.descricao, tempo_min=mo.tempo_min, colaborador_id=mo.colaborador_id))

    db.commit()
    db.refresh(produto)
    vh = get_valor_hora_padrao(user, db)
    calc = calcular_produto(produto, vh)
    out = ProdutoDetalhe.model_validate(produto)
    out.__dict__.update(calc)
    return out


@router.get("/{id}", response_model=ProdutoDetalhe)
def detalhar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = db.query(Produto).filter(
        Produto.id == id, Produto.user_id == user.id
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    vh = get_valor_hora_padrao(user, db)
    calc = calcular_produto(produto, vh)
    out = ProdutoDetalhe.model_validate(produto)
    out.__dict__.update(calc)
    return out


@router.put("/{id}", response_model=ProdutoDetalhe)
def atualizar(
    id: int,
    dados: ProdutoUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = db.query(Produto).filter(
        Produto.id == id, Produto.user_id == user.id
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    if dados.nome is not None:
        produto.nome = dados.nome

    def _replace(model_class, field_name, items, **build):
        for obj in getattr(produto, field_name):
            db.delete(obj)
        if items is not None:
            for item in items:
                db.add(model_class(produto_id=produto.id, **build(item)))

    if dados.preparacoes is not None:
        for obj in produto.massas: db.delete(obj)
        for obj in produto.recheios: db.delete(obj)
        for p in dados.preparacoes:
            db.add(ProdutoMassa(produto_id=produto.id, receita_id=p.receita_id, quantidade_g=p.quantidade_g))
    if dados.ingredientes is not None:
        for obj in produto.ingredientes: db.delete(obj)
        for i in dados.ingredientes:
            db.add(ProdutoIngrediente(produto_id=produto.id, ingrediente_id=i.ingrediente_id, quantidade_g=i.quantidade_g))
    if dados.embalagens is not None:
        for obj in produto.embalagens: db.delete(obj)
        for e in dados.embalagens:
            db.add(ProdutoEmbalagem(produto_id=produto.id, embalagem_id=e.embalagem_id, quantidade=e.quantidade))
    if dados.mo_montagem is not None:
        for obj in produto.mo_montagem: db.delete(obj)
        for mo in dados.mo_montagem:
            db.add(ProdutoMOMontagem(produto_id=produto.id, descricao=mo.descricao, tempo_min=mo.tempo_min, colaborador_id=mo.colaborador_id))

    db.commit()
    db.refresh(produto)
    vh = get_valor_hora_padrao(user, db)
    calc = calcular_produto(produto, vh)
    out = ProdutoDetalhe.model_validate(produto)
    out.__dict__.update(calc)
    return out


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = db.query(Produto).filter(
        Produto.id == id, Produto.user_id == user.id
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    produto.ativo = False
    db.commit()
