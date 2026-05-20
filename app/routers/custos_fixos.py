from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.auth.utils import get_usuario_atual
from app.models.models import User, CustoFixo, PeriodoEnum
from app.schemas.custos_fixos import CustoFixoCreate, CustoFixoUpdate, CustoFixoOut

router = APIRouter(prefix="/custos-fixos", tags=["Custos Fixos"])


def to_out(cf: CustoFixo) -> CustoFixoOut:
    valor_mensal = cf.valor if cf.periodo == PeriodoEnum.mensal else cf.valor / 12
    return CustoFixoOut(
        id=cf.id,
        nome=cf.nome,
        valor=cf.valor,
        periodo=cf.periodo,
        criado_em=cf.criado_em,
        valor_mensal=valor_mensal,
    )


@router.get("/", response_model=List[CustoFixoOut])
def listar(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    custos = db.query(CustoFixo).filter(CustoFixo.user_id == user.id).all()
    return [to_out(cf) for cf in custos]


@router.get("/resumo")
def resumo(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    custos = db.query(CustoFixo).filter(CustoFixo.user_id == user.id).all()
    total_mensal = sum(
        cf.valor if cf.periodo == PeriodoEnum.mensal else cf.valor / 12
        for cf in custos
    )
    return {"total_mensal": total_mensal, "total_anual": total_mensal * 12, "quantidade": len(custos)}


@router.post("/", response_model=CustoFixoOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: CustoFixoCreate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    cf = CustoFixo(user_id=user.id, **dados.model_dump())
    db.add(cf)
    db.commit()
    db.refresh(cf)
    return to_out(cf)


@router.put("/{id}", response_model=CustoFixoOut)
def atualizar(
    id: int,
    dados: CustoFixoUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    cf = db.query(CustoFixo).filter(CustoFixo.id == id, CustoFixo.user_id == user.id).first()
    if not cf:
        raise HTTPException(status_code=404, detail="Custo fixo não encontrado")
    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(cf, campo, valor)
    db.commit()
    db.refresh(cf)
    return to_out(cf)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(
    id: int,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    cf = db.query(CustoFixo).filter(CustoFixo.id == id, CustoFixo.user_id == user.id).first()
    if not cf:
        raise HTTPException(status_code=404, detail="Custo fixo não encontrado")
    db.delete(cf)
    db.commit()
