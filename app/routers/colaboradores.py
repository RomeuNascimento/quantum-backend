from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.auth.utils import get_usuario_atual
from app.models.models import User, Colaborador

router = APIRouter(prefix="/colaboradores", tags=["Colaboradores"])


class ColaboradorCreate(BaseModel):
    nome: str
    valor_hora: float


class ColaboradorUpdate(BaseModel):
    nome: Optional[str] = None
    valor_hora: Optional[float] = None
    ativo: Optional[bool] = None


class ColaboradorOut(BaseModel):
    id: int
    nome: str
    valor_hora: float
    ativo: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ColaboradorOut])
def listar(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    return db.query(Colaborador).filter(
        Colaborador.user_id == user.id, Colaborador.ativo == True
    ).all()


@router.post("/", response_model=ColaboradorOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: ColaboradorCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    colab = Colaborador(user_id=user.id, nome=dados.nome, valor_hora=dados.valor_hora)
    db.add(colab)
    db.commit()
    db.refresh(colab)
    return colab


@router.put("/{id}", response_model=ColaboradorOut)
def atualizar(
    id: int,
    dados: ColaboradorUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    colab = db.query(Colaborador).filter(
        Colaborador.id == id, Colaborador.user_id == user.id
    ).first()
    if not colab:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(colab, campo, valor)
    db.commit()
    db.refresh(colab)
    return colab


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    colab = db.query(Colaborador).filter(
        Colaborador.id == id, Colaborador.user_id == user.id
    ).first()
    if not colab:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    colab.ativo = False
    db.commit()
