from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.models.models import UnidadeEnum, OrigemEnum


class IngredientePrecoCreate(BaseModel):
    preco: float = Field(ge=0)
    quantidade_embalagem: float = Field(gt=0)
    data_compra: datetime
    origem: OrigemEnum = OrigemEnum.manual
    observacao: Optional[str] = None


class IngredientePrecoOut(BaseModel):
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


class IngredienteCreate(BaseModel):
    nome: str = Field(min_length=1)
    marca: Optional[str] = None
    unidade: UnidadeEnum
    fator_correcao: float = Field(default=1.0, gt=0)
    preco_inicial: Optional[IngredientePrecoCreate] = None


class IngredienteUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    marca: Optional[str] = None
    unidade: Optional[UnidadeEnum] = None
    fator_correcao: Optional[float] = Field(default=None, gt=0)


class IngredienteOut(BaseModel):
    id: int
    nome: str
    marca: Optional[str] = None
    unidade: UnidadeEnum
    fator_correcao: float
    ativo: bool
    criado_em: datetime
    custo_unitario_atual: Optional[float] = None  # calculado

    class Config:
        from_attributes = True


class IngredienteDetalhe(IngredienteOut):
    historico_precos: List[IngredientePrecoOut] = []
