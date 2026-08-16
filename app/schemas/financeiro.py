from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# Categorias sugeridas (a IA classifica dentro delas; o campo aceita texto livre
# para não travar o usuário — validação dura viraria atrito, não segurança)
CATEGORIAS_SAIDA = ["insumos", "embalagem", "transporte", "contas", "equipamento", "pessoal", "outros"]
CATEGORIAS_ENTRADA = ["venda", "encomenda", "outros"]

ORIGENS_VALIDAS = {"manual", "ia_texto", "comprovante", "nota", "whatsapp"}


class LancamentoCreate(BaseModel):
    tipo: Literal["entrada", "saida"]
    valor: float = Field(gt=0)
    descricao: Optional[str] = Field(default=None, max_length=200)
    categoria: Optional[str] = Field(default=None, max_length=50)
    data: Optional[date] = None  # default: hoje (aplicado no router)
    origem: str = "manual"


class LancamentoOut(BaseModel):
    id: int
    tipo: str
    valor: float
    descricao: Optional[str]
    categoria: Optional[str]
    data: date
    origem: str
    criado_em: Optional[datetime]

    model_config = {"from_attributes": True}


class CategoriaTotal(BaseModel):
    categoria: str
    total: float


class ResumoFinanceiro(BaseModel):
    mes: str                      # "YYYY-MM"
    entradas: float
    saidas: float
    sobra: float
    quantidade: int
    saidas_por_categoria: List[CategoriaTotal]
