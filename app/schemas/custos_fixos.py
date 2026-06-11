from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from app.models.models import PeriodoEnum


class CustoFixoCreate(BaseModel):
    nome: str = Field(min_length=1)
    valor: float = Field(ge=0)
    periodo: PeriodoEnum


class CustoFixoUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    valor: Optional[float] = Field(default=None, ge=0)
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
