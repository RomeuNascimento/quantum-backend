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
    # Atrás do reverse proxy (EasyPanel/Traefik), client.host é o IP do proxy —
    # todos os clientes cairiam no mesmo bucket de rate limit. O proxy ANEXA o
    # IP real ao fim do X-Forwarded-For, então o último valor é o único que ele
    # garante (os anteriores podem ser forjados pelo cliente).
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "desconhecido"


# Hash dummy verificado quando o e-mail não existe: iguala o tempo de resposta
# de "usuário inexistente" e "senha errada" (anti-enumeração por timing)
_DUMMY_HASH = hash_senha("timing-equalizer-nao-e-senha-real")


# Mensagem deliberadamente vaga: não confirma que o e-mail existe na base
# (anti-enumeração). O rate limit por IP impede varredura mesmo assim.
_MSG_REGISTRO_INDISPONIVEL = "Não foi possível criar a conta com estes dados. Verifique o e-mail ou faça login."


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def registrar(dados: UserCreate, request: Request, db: Session = Depends(get_db)):
    _register_limiter.checar(_ip(request))
    if db.query(User).filter(User.email == dados.email).first():
        raise HTTPException(status_code=400, detail=_MSG_REGISTRO_INDISPONIVEL)

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
        raise HTTPException(status_code=400, detail=_MSG_REGISTRO_INDISPONIVEL)
    db.refresh(user)

    token = criar_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
def login(dados: UserLogin, request: Request, db: Session = Depends(get_db)):
    _login_limiter.checar(_ip(request))
    user = db.query(User).filter(User.email == dados.email).first()
    senha_ok = verificar_senha(dados.senha, user.senha_hash if user else _DUMMY_HASH)
    if not user or not senha_ok:
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
