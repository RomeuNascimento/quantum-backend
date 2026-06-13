import uuid
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db, get_settings
from app.models.models import User, RevokedToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

CREDENCIAL_INVALIDA = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas ou sessão expirada",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, hash: str) -> bool:
    return pwd_context.verify(senha, hash)


def criar_token(data: dict) -> str:
    settings = get_settings()
    payload = data.copy()
    # jti: identifica o token para revogação individual (denylist no logout).
    payload.setdefault("jti", uuid.uuid4().hex)
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.jwt_expiration)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def criar_token_usuario(user: User) -> str:
    """Token de sessão: carrega o `tv` (token_version) atual do usuário, para
    que um bump em token_version (logout-all / troca de senha) o invalide."""
    return criar_token({"sub": str(user.id), "tv": user.token_version})


def decodificar_token(token: str) -> dict:
    """Decodifica e valida assinatura/expiração. Não checa revogação."""
    try:
        settings = get_settings()
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise CREDENCIAL_INVALIDA


def get_usuario_atual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decodificar_token(token)
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise CREDENCIAL_INVALIDA

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise CREDENCIAL_INVALIDA

    # Revogação em massa: tokens antigos sem `tv` contam como tv=0; bumpar
    # token_version (logout-all / troca de senha) invalida todos eles.
    if payload.get("tv", 0) != user.token_version:
        raise CREDENCIAL_INVALIDA

    # Revogação individual: jti na denylist (logout de um dispositivo).
    jti = payload.get("jti")
    if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise CREDENCIAL_INVALIDA

    return user
