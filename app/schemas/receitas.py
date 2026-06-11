from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class ReceitaIngredienteCreate(BaseModel):
    ingrediente_id: int
    quantidade_g: float = Field(gt=0)


class ReceitaIngredienteOut(BaseModel):
    id: int
    ingrediente_id: int
    ingrediente_nome: str
    unidade: str
    quantidade_g: float
    custo: float  # calculado

    class Config:
        from_attributes = True


class ReceitaMOEtapaCreate(BaseModel):
    descricao: str
    tempo_min: float = Field(ge=0)
    colaborador_id: Optional[int] = None


class ReceitaMOEtapaOut(BaseModel):
    id: int
    descricao: str
    tempo_min: float
    colaborador_id: Optional[int]
    colaborador_nome: Optional[str]
    valor_hora: float  # calculado: do colaborador ou valor_hora_padrao
    custo: float  # calculado

    class Config:
        from_attributes = True


class ReceitaCreate(BaseModel):
    nome: str = Field(min_length=1)
    tipo: Optional[str] = None
    rendimento_g: float = Field(gt=0)
    ingredientes: List[ReceitaIngredienteCreate] = []
    etapas_mo: List[ReceitaMOEtapaCreate] = []


class ReceitaUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    tipo: Optional[str] = None
    rendimento_g: Optional[float] = Field(default=None, gt=0)
    ingredientes: Optional[List[ReceitaIngredienteCreate]] = None
    etapas_mo: Optional[List[ReceitaMOEtapaCreate]] = None


class ReceitaOut(BaseModel):
    id: int
    nome: str
    tipo: Optional[str] = None
    rendimento_g: float
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True


class ReceitaDetalhe(ReceitaOut):
    ingredientes: List[ReceitaIngredienteOut] = []
    etapas_mo: List[ReceitaMOEtapaOut] = []
    custo_mp_total: float = 0.0
    custo_mo_total: float = 0.0
    custo_total: float = 0.0
    custo_por_grama: float = 0.0
