from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ProdutoPreparacaoCreate(BaseModel):
    receita_id: int
    quantidade_g: float


class ProdutoIngredienteCreate(BaseModel):
    ingrediente_id: int
    quantidade_g: float


class ProdutoEmbalagemCreate(BaseModel):
    embalagem_id: int
    quantidade: float


class ProdutoMOMontagemCreate(BaseModel):
    descricao: str
    tempo_min: float
    colaborador_id: Optional[int] = None


class PrepOut(BaseModel):
    id: int
    receita_id: int
    nome: str
    quantidade: float
    custo: float


class IngAvulsoOut(BaseModel):
    id: int
    ingrediente_id: int
    nome: str
    quantidade: float
    custo: float


class EmbOut(BaseModel):
    id: int
    embalagem_id: int
    nome: str
    quantidade: float
    custo: float


# mantido para compatibilidade interna
class ComponenteOut(BaseModel):
    id: int
    nome: str
    quantidade: float
    custo: float


class ProdutoMOMontagemOut(BaseModel):
    id: int
    descricao: str
    tempo_min: float
    colaborador_nome: Optional[str]
    custo: float

    class Config:
        from_attributes = True


class ProdutoCreate(BaseModel):
    nome: str
    preparacoes: List[ProdutoPreparacaoCreate] = []
    ingredientes: List[ProdutoIngredienteCreate] = []
    embalagens: List[ProdutoEmbalagemCreate] = []
    mo_montagem: List[ProdutoMOMontagemCreate] = []


class ProdutoUpdate(BaseModel):
    nome: Optional[str] = None
    preparacoes: Optional[List[ProdutoPreparacaoCreate]] = None
    ingredientes: Optional[List[ProdutoIngredienteCreate]] = None
    embalagens: Optional[List[ProdutoEmbalagemCreate]] = None
    mo_montagem: Optional[List[ProdutoMOMontagemCreate]] = None


class ProdutoOut(BaseModel):
    id: int
    nome: str
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True


class ProdutoDetalhe(ProdutoOut):
    preparacoes: List[PrepOut] = []
    ingredientes_avulsos: List[IngAvulsoOut] = []
    embalagens: List[EmbOut] = []
    mo_montagem: List[ProdutoMOMontagemOut] = []
    custo_mp_total: float = 0.0
    custo_mo_total: float = 0.0
    custo_embalagens_total: float = 0.0
    custo_total: float = 0.0
