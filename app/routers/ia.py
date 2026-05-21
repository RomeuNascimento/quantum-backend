import base64
import json
import os

import anthropic
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.utils import get_usuario_atual
from app.models.models import User

router = APIRouter(prefix="/ia", tags=["IA"])

UNIDADES_VALIDAS = {"g", "kg", "ml", "L", "unid"}

PROMPT_NOTA = """Analise esta nota fiscal ou cupom e extraia todos os itens listados.

Para cada item retorne:
- nome: nome genérico/comum do produto em português (ex: "Farinha de trigo", "Achocolatado", "Manteiga") — NÃO o código fiscal abreviado
- marca: marca comercial do produto (ex: "Nestlé", "Fleischmann", "Quaker") ou null se não identificada
- quantidade: quantidade numérica comprada (só o número)
- unidade: "g", "kg", "ml", "L" ou "unid"
- preco_total: valor total pago pelo item (só o número, sem R$)

Inclua TODOS os itens, inclusive não-alimentos.
Tente identificar a data da compra.

Retorne SOMENTE JSON válido, sem markdown, neste formato:
{"data_compra": "YYYY-MM-DD", "itens": [{"nome": "...", "marca": null, "quantidade": 1.0, "unidade": "unid", "preco_total": 0.0}]}

Se a data não estiver visível use null."""

PROMPT_RECEITAS = """Analise este documento e extraia todas as receitas culinárias presentes.

Para cada receita retorne:
- nome: nome da receita
- tipo: categoria livre ("Base", "Recheio", "Molho", "Acompanhamento" etc.) ou null
- rendimento_g: rendimento total estimado em gramas (número)
- ingredientes: lista com nome (string) e quantidade_g (número em gramas) de cada ingrediente
- etapas_mo: etapas de preparo, cada uma com descricao (string) e tempo_min estimado (número)

Retorne SOMENTE JSON válido, sem markdown, neste formato:
{"receitas": [{"nome": "...", "tipo": null, "rendimento_g": 0.0, "ingredientes": [{"nome": "...", "quantidade_g": 0.0}], "etapas_mo": [{"descricao": "...", "tempo_min": 5.0}]}]}"""


def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY não configurada no servidor.")
    return anthropic.Anthropic(api_key=key)


def _model():
    return os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")


def _parse(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


def _image_block(content: bytes, media_type: str) -> dict:
    b64 = base64.standard_b64encode(content).decode()
    if "pdf" in media_type:
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
    mt = media_type if media_type in {"image/jpeg", "image/png", "image/gif", "image/webp"} else "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}}


@router.post("/nota-fiscal")
async def processar_nota_fiscal(
    file: UploadFile = File(...),
    user: User = Depends(get_usuario_atual),
):
    content = await file.read()
    block = _image_block(content, file.content_type or "image/jpeg")
    try:
        resp = _client().messages.create(
            model=_model(),
            max_tokens=2048,
            messages=[{"role": "user", "content": [block, {"type": "text", "text": PROMPT_NOTA}]}],
        )
        data = _parse(resp.content[0].text)
        # Normalise units
        for item in data.get("itens", []):
            if item.get("unidade") not in UNIDADES_VALIDAS:
                item["unidade"] = "unid"
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="A IA retornou um formato inesperado. Tente novamente.")
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/receitas")
async def processar_receitas(
    file: UploadFile = File(...),
    user: User = Depends(get_usuario_atual),
):
    content = await file.read()
    mt = file.content_type or ""

    is_text = any(t in mt for t in ("spreadsheet", "excel", "csv", "plain", "text"))
    if is_text:
        texto = content.decode("utf-8", errors="replace")
        messages = [{"role": "user", "content": f"Conteúdo do arquivo:\n\n{texto}\n\n{PROMPT_RECEITAS}"}]
    else:
        block = _image_block(content, mt or "image/jpeg")
        messages = [{"role": "user", "content": [block, {"type": "text", "text": PROMPT_RECEITAS}]}]

    try:
        resp = _client().messages.create(model=_model(), max_tokens=4096, messages=messages)
        return _parse(resp.content[0].text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="A IA retornou um formato inesperado. Tente novamente.")
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=str(e))
