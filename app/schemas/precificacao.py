from pydantic import BaseModel, Field
from typing import Optional


class CanalCreate(BaseModel):
    nome: str = Field(min_length=1)
    taxa_plataforma_pct: float = Field(default=0.0, ge=0, lt=100)
    taxa_cartao_pct: float = Field(default=0.0, ge=0, lt=100)
    imposto_pct: float = Field(default=0.0, ge=0, lt=100)


class CanalUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    taxa_plataforma_pct: Optional[float] = Field(default=None, ge=0, lt=100)
    taxa_cartao_pct: Optional[float] = Field(default=None, ge=0, lt=100)
    imposto_pct: Optional[float] = Field(default=None, ge=0, lt=100)
    ativo: Optional[bool] = None


class CanalOut(BaseModel):
    id: int
    nome: str
    taxa_plataforma_pct: float
    taxa_cartao_pct: float
    imposto_pct: float
    ativo: bool

    class Config:
        from_attributes = True


class ProdutoPrecoCreate(BaseModel):
    canal_id: int
    margem_pct: float = Field(ge=0, lt=100)
    preco_final: Optional[float] = Field(default=None, gt=0)


class ProdutoPrecoUpdate(BaseModel):
    margem_pct: Optional[float] = Field(default=None, ge=0, lt=100)
    preco_final: Optional[float] = Field(default=None, gt=0)


class ProdutoPrecoOut(BaseModel):
    id: int
    produto_id: int
    canal_id: int
    canal_nome: str
    margem_pct: float
    preco_final: Optional[float]
    preco_sugerido: float  # calculado
    custo_total: float  # calculado

    class Config:
        from_attributes = True
