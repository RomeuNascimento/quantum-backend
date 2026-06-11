from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class UserCreate(BaseModel):
    nome: str = Field(min_length=1)
    email: EmailStr
    # max 72: bcrypt trunca silenciosamente acima disso
    senha: str = Field(min_length=8, max_length=72)


class UserLogin(BaseModel):
    email: EmailStr
    senha: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    nome: str
    email: str
    criado_em: datetime

    class Config:
        from_attributes = True


class ConfiguracaoOut(BaseModel):
    valor_hora_padrao: float

    class Config:
        from_attributes = True


class ConfiguracaoUpdate(BaseModel):
    valor_hora_padrao: float
