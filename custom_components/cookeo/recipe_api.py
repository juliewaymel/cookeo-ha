"""Accès aux recettes Cookeo via l'API Groupe SEB.

Découvert par reverse-engineering de l'app « Mon Cookeo » (07/06/2026) :
  * binaire `.cok` et images sur `/statics/...` — PUBLIC, sans auth.
  * fiche recette `/common-api/recipes/PRO/{fid}/` — header **`apikey`** requis
    (clé du domaine PRO_COO, dans `assets/domain.json` de l'app).

Il n'existe pas d'endpoint de *liste/recherche* public : le browse de l'app passe
par la synchro + les recommandations appareil. On récupère donc une recette par son
**id fonctionnel** (entier). L'envoi `.cok` reste public (UUID/URL).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from aiohttp import ClientSession

from .const import (
    BINARY_URL,
    IMAGE_URL,
    RECIPE_CONTENT_ENDPOINT,
    SEB_API_KEY,
)

_LOGGER = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)


def cok_url(uuid: str) -> str:
    """URL publique du binaire .cok pour un UUID."""
    return BINARY_URL.format(uuid=uuid)


def image_url(uuid: str, size: str = "medium") -> str:
    return IMAGE_URL.format(size=size, uuid=uuid)


def extract_uuid(text: str) -> str | None:
    m = _UUID_RE.search(text or "")
    return m.group(0) if m else None


def _api_headers(api_key: str | None) -> dict[str, str]:
    """En-têtes du catalogue SEB. Le header `apikey` est celui validé en RE."""
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 12) MonCookeo",
        "Accept": "application/json",
        "apikey": api_key or SEB_API_KEY,
    }


async def download_cok(session: ClientSession, url_or_uuid: str) -> bytes:
    """Télécharge un binaire .cok depuis une URL complète ou un simple UUID."""
    url = (url_or_uuid or "").strip()
    if not url:
        raise ValueError("UUID/URL .cok vide")
    if not url.startswith("http"):
        uuid = extract_uuid(url) or url
        url = cok_url(uuid)
    async with session.get(url) as resp:
        resp.raise_for_status()
        data = await resp.read()
    if data[:4] != b"COOK":
        _LOGGER.warning("Binaire %s sans magic COOK (taille %d)", url, len(data))
    return data


async def get_recipe(
    session: ClientSession, fid: str | int, api_key: str | None = None
) -> dict[str, Any]:
    """Fiche recette complète (JSON brut) par id fonctionnel. Header `apikey`."""
    url = RECIPE_CONTENT_ENDPOINT.format(fid=fid)
    async with session.get(url, headers=_api_headers(api_key)) as resp:
        if resp.status in (401, 403):
            raise PermissionError(
                "Catalogue SEB refusé (clé apikey invalide ?). Vérifiez la clé dans les options."
            )
        resp.raise_for_status()
        return await resp.json()


def parse_recipe_card(payload: dict[str, Any]) -> dict[str, Any]:
    """Extrait titre / image / ingrédients / étapes / binaire .cok pour l'affichage."""
    ident = payload.get("identifier") or {}
    cover = (payload.get("cover") or {}).get("media") or {}
    yield_ = payload.get("yield") or {}

    ingredients: list[str] = []
    for ing in payload.get("aggregatedIngredients") or payload.get("ingredients") or []:
        if isinstance(ing, dict):
            label = ing.get("name") or ing.get("title") or ing.get("label")
            if label:
                ingredients.append(label)

    steps: list[str] = []
    for st in payload.get("steps") or []:
        if isinstance(st, dict):
            txt = st.get("title") or st.get("instruction") or st.get("description")
            if txt:
                steps.append(re.sub(r"<[^>]+>", "", str(txt)).strip())

    # binaire .cok éventuel (selon le payload, sinon via la variante v3)
    cok = None
    for b in payload.get("binaries") or []:
        if isinstance(b, dict) and b.get("url"):
            cok = b["url"]
            break

    return {
        "fid": ident.get("functionalId"),
        "title": payload.get("title"),
        "lang": payload.get("lang"),
        "market": payload.get("market"),
        "yield": yield_.get("quantityDisplay"),
        "image": cover.get("medium") or cover.get("original") or cover.get("thumbnail"),
        "image_uuid": extract_uuid(cover.get("key", "")),
        "ingredients": ingredients,
        "steps": steps,
        "cok_url": cok,
        "grouping_id": payload.get("groupingId"),
    }


async def get_recipe_card(
    session: ClientSession, fid: str | int, api_key: str | None = None
) -> dict[str, Any]:
    """Fiche recette prête à afficher (titre/image/ingrédients/étapes)."""
    return parse_recipe_card(await get_recipe(session, fid, api_key))
