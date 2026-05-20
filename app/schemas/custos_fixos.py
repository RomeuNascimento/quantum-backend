from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.models import PeriodoEnum


class CustoFixoCreate(BaseModel):
    nome: str
    valor: float
    periodo: PeriodoEnum


class CustoFixoUpdate(BaseModel):
    nome: Optional[str] = None
    valor: Optional[float] = None
    periodo: Optional[PeriodoEnum] = None


class CustoFixoOut(BaseModel):
    id: int
    nome: str
    valor: float
    periodo: PeriodoEnum
    criado_em: datetime
    valor_mensal: float  # calculado: valor se mensal, valor/12 se anual

    class Config:
        from_attributes = True
