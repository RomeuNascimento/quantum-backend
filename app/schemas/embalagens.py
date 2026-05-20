from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.models.models import UnidadeEnum, OrigemEnum


class EmbalagemPrecoCreate(BaseModel):
    preco: float
    quantidade_embalagem: float
    data_compra: datetime
    origem: OrigemEnum = OrigemEnum.manual
    observacao: Optional[str] = None


class EmbalagemPrecoOut(BaseModel):
    id: int
    preco: float
    quantidade_embalagem: float
    data_compra: datetime
    origem: OrigemEnum
    observacao: Optional[str]
    criado_em: datetime
    custo_unitario: float  # calculado

    class Config:
        from_attributes = True


class EmbalagemCreate(BaseModel):
    nome: str
    unidade: UnidadeEnum
    preco_inicial: Optional[EmbalagemPrecoCreate] = None


class EmbalagemUpdate(BaseModel):
    nome: Optional[str] = None
    unidade: Optional[UnidadeEnum] = None


class EmbalagemOut(BaseModel):
    id: int
    nome: str
    unidade: UnidadeEnum
    ativo: bool
    criado_em: datetime
    custo_unitario_atual: Optional[float] = None  # calculado

    class Config:
        from_attributes = True


class EmbalagemDetalhe(EmbalagemOut):
    historico_precos: List[EmbalagemPrecoOut] = []
