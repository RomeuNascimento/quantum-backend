from fastapi import HTTPException
from sqlalchemy.orm import Session


def validar_ids_do_usuario(db: Session, model, ids, user_id: int, nome_entidade: str):
    """Garante que todos os IDs referenciados pertencem ao usuário autenticado.

    Levanta 404 (mesmo status dos GETs) para não revelar a existência de
    recursos de outros tenants.
    """
    ids = {i for i in ids if i is not None}
    if not ids:
        return
    encontrados = {
        row[0]
        for row in db.query(model.id)
        .filter(model.id.in_(ids), model.user_id == user_id)
        .all()
    }
    faltando = ids - encontrados
    if faltando:
        raise HTTPException(
            status_code=404,
            detail=f"{nome_entidade} {min(faltando)} não encontrado",
        )
