from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.auth.utils import get_usuario_atual
from app.models.models import (
    User, Receita, ReceitaIngrediente, ReceitaMOEtapa,
    Ingrediente, IngredientePreco, Colaborador, Configuracao
)
from app.schemas.receitas import (
    ReceitaCreate, ReceitaUpdate, ReceitaOut, ReceitaDetalhe,
    ReceitaIngredienteOut, ReceitaMOEtapaOut
)

router = APIRouter(prefix="/receitas", tags=["Receitas"])


def custo_unitario_ingrediente(ingrediente: Ingrediente) -> float:
    precos = sorted(ingrediente.precos, key=lambda p: p.data_compra, reverse=True)
    if not precos:
        return 0.0
    p = precos[0]
    if p.quantidade_embalagem == 0 or ingrediente.fator_correcao == 0:
        return 0.0
    return (p.preco / p.quantidade_embalagem) / ingrediente.fator_correcao


def calcular_receita(receita: Receita, valor_hora_padrao: float) -> dict:
    custo_mp = 0.0
    ingredientes_out = []
    for ri in receita.ingredientes:
        cu = custo_unitario_ingrediente(ri.ingrediente)
        custo = cu * ri.quantidade_g
        custo_mp += custo
        ingredientes_out.append(ReceitaIngredienteOut(
            id=ri.id,
            ingrediente_id=ri.ingrediente_id,
            ingrediente_nome=ri.ingrediente.nome,
            unidade=ri.ingrediente.unidade,
            quantidade_g=ri.quantidade_g,
            custo=custo,
        ))

    custo_mo = 0.0
    etapas_out = []
    for etapa in receita.etapas_mo:
        if etapa.colaborador_id and etapa.colaborador:
            vh = etapa.colaborador.valor_hora
            nome_colab = etapa.colaborador.nome
        else:
            vh = valor_hora_padrao
            nome_colab = None
        custo_etapa = (vh / 60) * etapa.tempo_min
        custo_mo += custo_etapa
        etapas_out.append(ReceitaMOEtapaOut(
            id=etapa.id,
            descricao=etapa.descricao,
            tempo_min=etapa.tempo_min,
            colaborador_id=etapa.colaborador_id,
            colaborador_nome=nome_colab,
            valor_hora=vh,
            custo=custo_etapa,
        ))

    custo_total = custo_mp + custo_mo
    custo_por_grama = custo_total / receita.rendimento_g if receita.rendimento_g > 0 else 0.0

    return {
        "ingredientes": ingredientes_out,
        "etapas_mo": etapas_out,
        "custo_mp_total": custo_mp,
        "custo_mo_total": custo_mo,
        "custo_total": custo_total,
        "custo_por_grama": custo_por_grama,
    }


def get_valor_hora_padrao(user: User, db: Session) -> float:
    config = db.query(Configuracao).filter(Configuracao.user_id == user.id).first()
    return config.valor_hora_padrao if config else 0.0


@router.get("/", response_model=List[ReceitaOut])
def listar(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    return db.query(Receita).filter(
        Receita.user_id == user.id, Receita.ativo == True
    ).all()


@router.post("/", response_model=ReceitaDetalhe, status_code=status.HTTP_201_CREATED)
def criar(
    dados: ReceitaCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    receita = Receita(
        user_id=user.id,
        nome=dados.nome,
        tipo=dados.tipo,
        rendimento_g=dados.rendimento_g,
    )
    db.add(receita)
    db.flush()

    for ing_data in dados.ingredientes:
        ing = db.query(Ingrediente).filter(
            Ingrediente.id == ing_data.ingrediente_id, Ingrediente.user_id == user.id
        ).first()
        if not ing:
            raise HTTPException(status_code=404, detail=f"Ingrediente {ing_data.ingrediente_id} não encontrado")
        ri = ReceitaIngrediente(
            receita_id=receita.id,
            ingrediente_id=ing_data.ingrediente_id,
            quantidade_g=ing_data.quantidade_g,
        )
        db.add(ri)

    for etapa_data in dados.etapas_mo:
        etapa = ReceitaMOEtapa(
            receita_id=receita.id,
            descricao=etapa_data.descricao,
            tempo_min=etapa_data.tempo_min,
            colaborador_id=etapa_data.colaborador_id,
        )
        db.add(etapa)

    db.commit()
    db.refresh(receita)
    vh = get_valor_hora_padrao(user, db)
    calc = calcular_receita(receita, vh)
    out = ReceitaDetalhe.model_validate(receita)
    out.__dict__.update(calc)
    return out


@router.get("/{id}", response_model=ReceitaDetalhe)
def detalhar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    receita = db.query(Receita).filter(
        Receita.id == id, Receita.user_id == user.id
    ).first()
    if not receita:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    vh = get_valor_hora_padrao(user, db)
    calc = calcular_receita(receita, vh)
    out = ReceitaDetalhe.model_validate(receita)
    out.__dict__.update(calc)
    return out


@router.put("/{id}", response_model=ReceitaDetalhe)
def atualizar(
    id: int,
    dados: ReceitaUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    receita = db.query(Receita).filter(
        Receita.id == id, Receita.user_id == user.id
    ).first()
    if not receita:
        raise HTTPException(status_code=404, detail="Receita não encontrada")

    if dados.nome is not None:
        receita.nome = dados.nome
    if dados.tipo is not None:
        receita.tipo = dados.tipo
    if dados.rendimento_g is not None:
        receita.rendimento_g = dados.rendimento_g

    if dados.ingredientes is not None:
        for ri in receita.ingredientes:
            db.delete(ri)
        for ing_data in dados.ingredientes:
            db.add(ReceitaIngrediente(
                receita_id=receita.id,
                ingrediente_id=ing_data.ingrediente_id,
                quantidade_g=ing_data.quantidade_g,
            ))

    if dados.etapas_mo is not None:
        for etapa in receita.etapas_mo:
            db.delete(etapa)
        for etapa_data in dados.etapas_mo:
            db.add(ReceitaMOEtapa(
                receita_id=receita.id,
                descricao=etapa_data.descricao,
                tempo_min=etapa_data.tempo_min,
                colaborador_id=etapa_data.colaborador_id,
            ))

    db.commit()
    db.refresh(receita)
    vh = get_valor_hora_padrao(user, db)
    calc = calcular_receita(receita, vh)
    out = ReceitaDetalhe.model_validate(receita)
    out.__dict__.update(calc)
    return out


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    receita = db.query(Receita).filter(
        Receita.id == id, Receita.user_id == user.id
    ).first()
    if not receita:
        raise HTTPException(status_code=404, detail="Receita não encontrada")

    from app.models.models import ProdutoMassa, ProdutoRecheio
    em_uso = (
        db.query(ProdutoMassa).filter(ProdutoMassa.receita_id == id).first()
        or db.query(ProdutoRecheio).filter(ProdutoRecheio.receita_id == id).first()
    )
    if em_uso:
        receita.ativo = False
        db.commit()
    else:
        db.delete(receita)
        db.commit()
