"""Accès aux recettes Cookeo via l'API Groupe SEB.

Deux niveaux :
  * binaire `.cok` sur `/statics/original/<uuid>.cok` — PUBLIC, sans auth (confirmé).
  * catalogue `/common-api/v3/recipes/PRO/...` — protégé (403 sans clé API).

L'envoi par UUID/URL fonctionne donc sans cloud. La recherche par mots-clés
nécessite une clé API (renseignée dans les options de l'intégration) ; sans clé,
elle lève une erreur explicite plutôt que d'échouer en silence.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from aiohttp import ClientSession

from .const import BINARY_URL, RECIPE_ENDPOINT, SEB_API

_LOGGER = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)
SEARCH_ENDPOINT = SEB_API + "/common-api/v3/recipes/PRO/"


def cok_url(uuid: str) -> str:
    """URL publique du binaire .cok pour un UUID."""
    return BINARY_URL.format(uuid=uuid)


def extract_uuid(text: str) -> str | None:
    m = _UUID_RE.search(text or "")
    return m.group(0) if m else None


async def download_cok(session: ClientSession, url_or_uuid: str) -> bytes:
    """Télécharge un binaire .cok depuis une URL complète ou un simple UUID."""
    url = url_or_uuid
    if not url_or_uuid.startswith("http"):
        uuid = extract_uuid(url_or_uuid) or url_or_uuid
        url = cok_url(uuid)
    async with session.get(url) as resp:
        resp.raise_for_status()
        data = await resp.read()
    if data[:4] != b"COOK":
        _LOGGER.warning("Binaire %s sans magic COOK (taille %d)", url, len(data))
    return data


def _api_headers(api_key: str | None) -> dict[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 12) MonCookeo",
        "Accept": "application/json",
    }
    if api_key:
        # En-tête le plus courant côté Groupe SEB ; ajusté si besoin via options.
        headers["x-api-key"] = api_key
        headers["apikey"] = api_key
    return headers


async def get_recipe(
    session: ClientSession, variant_id: str, api_key: str | None = None
) -> dict[str, Any]:
    """Métadonnées d'une recette (dont binaries[].url .cok). Catalogue protégé."""
    url = RECIPE_ENDPOINT.format(variant_id=variant_id)
    async with session.get(url, headers=_api_headers(api_key)) as resp:
        if resp.status == 403:
            raise PermissionError(
                "Catalogue SEB protégé (403) : renseignez une clé API dans les options "
                "ou utilisez directement l'UUID/URL du .cok."
            )
        resp.raise_for_status()
        return await resp.json()


def parse_recipe_meta(payload: dict[str, Any]) -> dict[str, Any]:
    """Extrait id / version / catégorie / url .cok depuis la réponse catalogue."""
    binaries = payload.get("binaries") or []
    if not binaries and payload.get("packs"):
        for pack in payload["packs"]:
            binaries = pack.get("binaries") or []
            if binaries:
                break
    binary = binaries[0] if binaries else {}
    fid = (payload.get("groupingId") or {}).get("functionalId") or payload.get("id", "")
    rid_match = re.search(r"(\d+)$", str(fid))
    return {
        "title": payload.get("title"),
        "recipe_id": int(rid_match.group(1)) if rid_match else None,
        "version": binary.get("version", "1.0"),
        "url": binary.get("url"),
        "checksum": binary.get("checksum"),
        "category": (payload.get("category") or {}).get("id", 2),
    }


async def search_recipes(
    session: ClientSession, query: str, api_key: str | None = None, size: int = 10
) -> list[dict[str, Any]]:
    """Recherche par mots-clés dans le catalogue PRO (nécessite une clé API)."""
    params = {"search": query, "size": str(size), "domain": "PRO_COO"}
    async with session.get(
        SEARCH_ENDPOINT, params=params, headers=_api_headers(api_key)
    ) as resp:
        if resp.status == 403:
            raise PermissionError(
                "Recherche catalogue SEB protégée (403). Renseignez une clé API dans "
                "les options de l'intégration Cookeo, ou envoyez par UUID/URL .cok."
            )
        resp.raise_for_status()
        payload = await resp.json()
    items = payload.get("content") or payload.get("results") or payload.get("hits") or []
    out: list[dict[str, Any]] = []
    for item in items[:size]:
        out.append(
            {
                "title": item.get("title") or item.get("name"),
                "variant_id": item.get("id") or item.get("variantId"),
                "uuid": extract_uuid(str(item)),
            }
        )
    return out
