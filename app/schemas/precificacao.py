from pydantic import BaseModel
from typing import Optional


class CanalCreate(BaseModel):
    nome: str
    taxa_plataforma_pct: float = 0.0
    taxa_cartao_pct: float = 0.0
    imposto_pct: float = 0.0


class CanalUpdate(BaseModel):
    nome: Optional[str] = None
    taxa_plataforma_pct: Optional[float] = None
    taxa_cartao_pct: Optional[float] = None
    imposto_pct: Optional[float] = None
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
    margem_pct: float
    preco_final: Optional[float] = None


class ProdutoPrecoUpdate(BaseModel):
    margem_pct: Optional[float] = None
    preco_final: Optional[float] = None


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
