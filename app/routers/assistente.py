"""Assistente — gravação transacional do fluxo guiado ("salvar tudo").

Recebe o produto montado nas 4 etapas (receita + preços + tempo + preço) e cria
de uma vez: ingredientes novos + seus preços + a receita + um produto (que
embrulha a receita) + a precificação. Tudo numa transação só — se algo falha,
nada é gravado.

Mapeamentos importantes:
- Ingrediente cobrado por UNIDADE (ovo): a quantidade na receita é a CONTAGEM
  (o frontend já manda 3, não 150g), coerente com a fórmula de custo do backend.
- Produto = 1 unidade vendável: a preparação usa `rendimento_g / porcoes`, então
  o custo do produto já sai por porção (o modelo de Produto não tem rendimento).
- Preço recomendado (venda direta): gravado num canal "Venda direta" (0% taxas),
  criado sob demanda se o usuário ainda não tiver.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.utils import get_usuario_atual
from app.database import get_db
from app.models.models import (
    Canal, Embalagem, EmbalagemPreco, Ingrediente, IngredientePreco, OrigemEnum,
    Produto, ProdutoEmbalagem, ProdutoMassa, ProdutoPreco, Receita,
    ReceitaIngrediente, ReceitaMOEtapa, UnidadeEnum, User,
)
from app.routers.ownership import validar_ids_do_usuario
from app.routers.billing import garantir_limite_produtos

router = APIRouter(prefix="/assistente", tags=["Assistente"])

CANAL_VENDA_DIRETA = "Venda direta"


class IngredienteAssistente(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    quantidade: float = Field(gt=0)  # consumo na receita (contagem p/ unid, g/ml senão)
    ingrediente_id: Optional[int] = None  # se já existe no catálogo
    # para ingrediente novo / registro de preço coletado nesta sessão:
    unidade: UnidadeEnum = UnidadeEnum.g
    preco: Optional[float] = Field(default=None, ge=0)
    quantidade_embalagem: Optional[float] = Field(default=None, gt=0)


class EtapaAssistente(BaseModel):
    descricao: str = Field(min_length=1, max_length=500)
    tempo_min: float = Field(ge=0)


class EmbalagemAssistente(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    preco: float = Field(gt=0)
    quantidade_embalagem: float = Field(default=1, gt=0)  # qtd no pacote comprado
    quantidade_usada: float = Field(default=1, gt=0)       # qtd por unidade do produto


class SalvarAssistenteRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    tipo: Optional[str] = Field(default=None, max_length=100)
    rendimento_g: float = Field(gt=0)
    porcoes: float = Field(default=1, gt=0)
    margem_pct: float = Field(ge=0, lt=100)
    etapas_mo: List[EtapaAssistente] = []  # vazio = sem mão de obra
    ingredientes: List[IngredienteAssistente] = Field(min_length=1)
    embalagens: List[EmbalagemAssistente] = []  # opcional


class SalvarAssistenteResposta(BaseModel):
    produto_id: int
    receita_id: int
    canal_id: int


def _get_ou_cria_venda_direta(db: Session, user_id: int) -> Canal:
    canal = (
        db.query(Canal)
        .filter(Canal.user_id == user_id, Canal.nome == CANAL_VENDA_DIRETA)
        .first()
    )
    if canal:
        return canal
    canal = Canal(
        user_id=user_id, nome=CANAL_VENDA_DIRETA,
        taxa_plataforma_pct=0.0, taxa_cartao_pct=0.0, imposto_pct=0.0, ativo=True,
    )
    db.add(canal)
    db.flush()
    return canal


@router.post("/salvar", response_model=SalvarAssistenteResposta, status_code=status.HTTP_201_CREATED)
def salvar(
    dados: SalvarAssistenteRequest,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    garantir_limite_produtos(user, db)  # freemium: tier grátis até N produtos
    # Ownership dos ingredientes existentes referenciados
    ids_existentes = [i.ingrediente_id for i in dados.ingredientes if i.ingrediente_id]
    validar_ids_do_usuario(db, Ingrediente, ids_existentes, user.id, "Ingrediente")

    agora = datetime.utcnow()

    # 1) Resolve cada ingrediente: usa o existente ou cria; registra preço coletado
    resolvidos = []  # (ingrediente_id, quantidade_consumida)
    for item in dados.ingredientes:
        if item.ingrediente_id:
            ing_id = item.ingrediente_id
        else:
            ing = Ingrediente(
                user_id=user.id, nome=item.nome,
                unidade=item.unidade, fator_correcao=1.0,
            )
            db.add(ing)
            db.flush()
            ing_id = ing.id

        if item.preco is not None and item.quantidade_embalagem:
            db.add(IngredientePreco(
                ingrediente_id=ing_id,
                preco=item.preco,
                quantidade_embalagem=item.quantidade_embalagem,
                data_compra=agora,
                origem=OrigemEnum.manual,
            ))

        resolvidos.append((ing_id, item.quantidade))

    # 2) Receita + ingredientes + etapas de mão de obra
    receita = Receita(user_id=user.id, nome=dados.nome, tipo=dados.tipo, rendimento_g=dados.rendimento_g)
    db.add(receita)
    db.flush()
    for ing_id, qtd in resolvidos:
        db.add(ReceitaIngrediente(receita_id=receita.id, ingrediente_id=ing_id, quantidade_g=qtd))
    for etapa in dados.etapas_mo:
        db.add(ReceitaMOEtapa(receita_id=receita.id, descricao=etapa.descricao, tempo_min=etapa.tempo_min))

    # 3) Produto = 1 unidade vendável (preparação usa rendimento/porcoes)
    produto = Produto(user_id=user.id, nome=dados.nome)
    db.add(produto)
    db.flush()
    qtd_por_unidade = dados.rendimento_g / dados.porcoes
    db.add(ProdutoMassa(produto_id=produto.id, receita_id=receita.id, quantidade_g=qtd_por_unidade))

    # 3b) Embalagens (opcional): cria embalagem + preço + vínculo com o produto
    for emb in dados.embalagens:
        embalagem = Embalagem(user_id=user.id, nome=emb.nome, unidade=UnidadeEnum.unid)
        db.add(embalagem)
        db.flush()
        db.add(EmbalagemPreco(
            embalagem_id=embalagem.id, preco=emb.preco,
            quantidade_embalagem=emb.quantidade_embalagem, data_compra=agora,
            origem=OrigemEnum.manual,
        ))
        db.add(ProdutoEmbalagem(produto_id=produto.id, embalagem_id=embalagem.id, quantidade=emb.quantidade_usada))

    # 4) Precificação no canal "Venda direta"
    canal = _get_ou_cria_venda_direta(db, user.id)
    db.add(ProdutoPreco(produto_id=produto.id, canal_id=canal.id, margem_pct=dados.margem_pct))

    db.commit()
    return SalvarAssistenteResposta(produto_id=produto.id, receita_id=receita.id, canal_id=canal.id)
