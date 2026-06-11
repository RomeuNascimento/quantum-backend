from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User, Configuracao, Canal
from app.auth.schemas import UserCreate, UserLogin, Token, UserOut, ConfiguracaoOut, ConfiguracaoUpdate
from app.auth.utils import hash_senha, verificar_senha, criar_token, get_usuario_atual
from app.ratelimit import RateLimiter

router = APIRouter(prefix="/auth", tags=["Autenticação"])

_login_limiter = RateLimiter(10, 300, "Muitas tentativas de login. Aguarde alguns minutos.")
_register_limiter = RateLimiter(5, 3600, "Muitas contas criadas a partir deste endereço. Tente mais tarde.")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def registrar(dados: UserCreate, request: Request, db: Session = Depends(get_db)):
    _register_limiter.checar(_ip(request))
    if db.query(User).filter(User.email == dados.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    user = User(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
    )
    db.add(user)
    db.flush()

    # Configuração padrão
    configuracao = Configuracao(user_id=user.id, valor_hora_padrao=0.0)
    db.add(configuracao)

    # Canal iFood pré-cadastrado
    ifood = Canal(
        user_id=user.id,
        nome="iFood",
        taxa_plataforma_pct=12.0,
        taxa_cartao_pct=2.99,
        imposto_pct=6.0,
        ativo=True,
    )
    db.add(ifood)
    try:
        db.commit()
    except IntegrityError:
        # Race no check-then-insert: dois registers simultâneos do mesmo e-mail
        db.rollback()
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    db.refresh(user)

    token = criar_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
def login(dados: UserLogin, request: Request, db: Session = Depends(get_db)):
    _login_limiter.checar(_ip(request))
    user = db.query(User).filter(User.email == dados.email).first()
    if not user or not verificar_senha(dados.senha, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )
    token = criar_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_usuario_atual)):
    return user


@router.get("/configuracao", response_model=ConfiguracaoOut)
def get_configuracao(
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    return user.configuracao


@router.put("/configuracao", response_model=ConfiguracaoOut)
def atualizar_configuracao(
    dados: ConfiguracaoUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    config = user.configuracao
    config.valor_hora_padrao = dados.valor_hora_padrao
    db.commit()
    db.refresh(config)
    return config
