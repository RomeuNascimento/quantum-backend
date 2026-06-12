from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from typing import List
from collections import defaultdict
from datetime import date as date_type
from app.database import get_db
from app.auth.utils import get_usuario_atual
from app.models.models import (
    User, Produto, ProdutoMassa, ProdutoRecheio, ProdutoIngrediente,
    ProdutoEmbalagem, ProdutoMOMontagem, Receita, ReceitaIngrediente,
    ReceitaMOEtapa, Ingrediente, Embalagem,
    Colaborador, IngredientePreco, EmbalagemPreco
)
from app.schemas.produtos import (
    ProdutoCreate, ProdutoUpdate, ProdutoOut, ProdutoDetalhe,
    PrepOut, IngAvulsoOut, EmbOut, ProdutoMOMontagemOut, ProdutoPreparacaoCreate,
    HistoricoOut, HistoricoPonto
)
from app.routers.receitas import calcular_receita, get_valor_hora_padrao, custo_unitario_ingrediente
from app.routers.ownership import validar_ids_do_usuario
from app.routers.custos import custo_unitario_de_preco, custo_unitario_embalagem_de_preco, preco_mais_recente

router = APIRouter(prefix="/produtos", tags=["Produtos"])


def _validar_componentes(db: Session, user: User, preparacoes, ingredientes, embalagens, mo_montagem):
    validar_ids_do_usuario(db, Receita, (p.receita_id for p in preparacoes or []), user.id, "Receita")
    validar_ids_do_usuario(db, Ingrediente, (i.ingrediente_id for i in ingredientes or []), user.id, "Ingrediente")
    validar_ids_do_usuario(db, Embalagem, (e.embalagem_id for e in embalagens or []), user.id, "Embalagem")
    validar_ids_do_usuario(db, Colaborador, (mo.colaborador_id for mo in mo_montagem or []), user.id, "Colaborador")


def query_produto_completo(db: Session):
    """Query de Produto com todos os relacionamentos usados por calcular_produto
    pré-carregados — sem isso a cascata lazy gera 30-80 queries por produto."""
    receita_completa = [
        selectinload(Receita.ingredientes)
        .selectinload(ReceitaIngrediente.ingrediente)
        .selectinload(Ingrediente.precos),
        selectinload(Receita.etapas_mo).selectinload(ReceitaMOEtapa.colaborador),
    ]
    return db.query(Produto).options(
        selectinload(Produto.massas).selectinload(ProdutoMassa.receita).options(*receita_completa),
        selectinload(Produto.recheios).selectinload(ProdutoRecheio.receita).options(*receita_completa),
        selectinload(Produto.ingredientes)
        .selectinload(ProdutoIngrediente.ingrediente)
        .selectinload(Ingrediente.precos),
        selectinload(Produto.embalagens)
        .selectinload(ProdutoEmbalagem.embalagem)
        .selectinload(Embalagem.precos),
        selectinload(Produto.mo_montagem).selectinload(ProdutoMOMontagem.colaborador),
    )


def custo_unitario_embalagem(embalagem: Embalagem) -> float:
    return custo_unitario_embalagem_de_preco(preco_mais_recente(embalagem.precos))


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
    _validar_componentes(db, user, dados.preparacoes, dados.ingredientes, dados.embalagens, dados.mo_montagem)

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
    return ProdutoDetalhe(**ProdutoOut.model_validate(produto).model_dump(), **calc)


@router.get("/{id}", response_model=ProdutoDetalhe)
def detalhar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = query_produto_completo(db).filter(
        Produto.id == id, Produto.user_id == user.id
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    vh = get_valor_hora_padrao(user, db)
    calc = calcular_produto(produto, vh)
    return ProdutoDetalhe(**ProdutoOut.model_validate(produto).model_dump(), **calc)


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

    _validar_componentes(db, user, dados.preparacoes, dados.ingredientes, dados.embalagens, dados.mo_montagem)

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
    return ProdutoDetalhe(**ProdutoOut.model_validate(produto).model_dump(), **calc)


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


@router.get("/{id}/historico-custo", response_model=HistoricoOut)
def historico_custo(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    produto = query_produto_completo(db).filter(
        Produto.id == id, Produto.user_id == user.id
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    vh = get_valor_hora_padrao(user, db)

    # Prepara estrutura: preparações e ingredientes avulsos e embalagens
    prep_entries = [(pm.receita, pm.quantidade_g) for pm in list(produto.massas) + list(produto.recheios) if pm.receita]
    ing_avulso_entries = [(pi.ingrediente, pi.quantidade_g) for pi in produto.ingredientes]
    emb_entries = [(pe.embalagem, pe.quantidade) for pe in produto.embalagens]

    # IDs de ingredientes e embalagens necessários
    all_ing_ids = set()
    for receita, _ in prep_entries:
        for ri in receita.ingredientes:
            all_ing_ids.add(ri.ingrediente_id)
    for ing, _ in ing_avulso_entries:
        all_ing_ids.add(ing.id)

    all_emb_ids = {emb.id for emb, _ in emb_entries}

    # Histórico de preços
    ing_prices: dict = defaultdict(list)
    if all_ing_ids:
        for p in db.query(IngredientePreco).filter(IngredientePreco.ingrediente_id.in_(all_ing_ids)).all():
            ing_prices[p.ingrediente_id].append(p)

    emb_prices: dict = defaultdict(list)
    if all_emb_ids:
        for p in db.query(EmbalagemPreco).filter(EmbalagemPreco.embalagem_id.in_(all_emb_ids)).all():
            emb_prices[p.embalagem_id].append(p)

    if not ing_prices and not emb_prices:
        return HistoricoOut(pontos=[])

    # Datas de mudança: toda nova entrada de preço cria um ponto
    all_dates = set()
    for prices in ing_prices.values():
        for p in prices:
            all_dates.add(p.data_compra.date())
    for prices in emb_prices.values():
        for p in prices:
            all_dates.add(p.data_compra.date())
    all_dates.add(date_type.today())
    dates = sorted(all_dates)

    def price_at(price_list, d):
        valid = [p for p in price_list if p.data_compra.date() <= d]
        return max(valid, key=lambda p: p.data_compra) if valid else None

    # MO de montagem não muda no tempo
    mo_montagem_custo = sum(
        ((mo.colaborador.valor_hora if mo.colaborador_id and mo.colaborador else vh) / 60) * mo.tempo_min
        for mo in produto.mo_montagem
    )

    pontos_raw = []
    for d in dates:
        custo = 0.0

        # Preparações (receitas vinculadas ao produto)
        for receita, qtd_usada in prep_entries:
            if receita.rendimento_g <= 0:
                continue
            fator = qtd_usada / receita.rendimento_g
            custo_mp_rec = 0.0
            for ri in receita.ingredientes:
                ing = ri.ingrediente
                p = price_at(ing_prices.get(ri.ingrediente_id, []), d)
                custo_mp_rec += custo_unitario_de_preco(p, ing.unidade, ing.fator_correcao) * ri.quantidade_g
            custo_mo_rec = sum(
                ((et.colaborador.valor_hora if et.colaborador_id and et.colaborador else vh) / 60) * et.tempo_min
                for et in receita.etapas_mo
            )
            custo += (custo_mp_rec + custo_mo_rec) * fator

        # Ingredientes avulsos
        for ing, qtd in ing_avulso_entries:
            p = price_at(ing_prices.get(ing.id, []), d)
            custo += custo_unitario_de_preco(p, ing.unidade, ing.fator_correcao) * qtd

        # Embalagens
        for emb, qtd in emb_entries:
            p = price_at(emb_prices.get(emb.id, []), d)
            custo += custo_unitario_embalagem_de_preco(p) * qtd

        custo += mo_montagem_custo
        pontos_raw.append(HistoricoPonto(data=d.isoformat(), custo=round(custo, 4)))

    # Mantém apenas pontos onde o custo mudou (+ sempre o primeiro e o último)
    result = [pontos_raw[0]]
    for pt in pontos_raw[1:]:
        if abs(pt.custo - result[-1].custo) > 0.001:
            result.append(pt)
    if result[-1].data != pontos_raw[-1].data:
        result.append(pontos_raw[-1])

    return HistoricoOut(pontos=result)
