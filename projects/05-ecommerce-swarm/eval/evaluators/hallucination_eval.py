"""Detecta claims inventados vs datos mock de Shopify."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from eval.mocks import MOCK_ORDERS, MOCK_PRODUCTS


def _extract_claims_heuristic(response: str) -> list[str]:
    claims = []
    for m in re.finditer(r"\$[\d.,]+\s*COP", response):
        claims.append(m.group(0))
    for m in re.finditer(r"#\d{3,5}", response):
        claims.append(m.group(0))
    for p in MOCK_PRODUCTS:
        if p["title"].lower() in response.lower():
            claims.append(p["title"])
    return claims


async def _extract_claims_llm(response: str, llm: Any) -> list[str]:
    prompt = (
        "Extrae claims verificables de productos, precios o pedidos de este texto. "
        'Responde SOLO JSON: {"claims": ["...", "..."]}\n\n' + response[:2000]
    )
    msg = await llm.ainvoke(prompt)
    raw = msg.content if hasattr(msg, "content") else str(msg)
    try:
        if "```" in raw:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            raw = m.group(0) if m else '{"claims": []}'
        return json.loads(raw).get("claims", [])
    except json.JSONDecodeError:
        return _extract_claims_heuristic(response)


def _verify_claim(claim: str) -> bool:
    cl = claim.lower()
    for p in MOCK_PRODUCTS:
        price_str = f"${p['price']:,}".replace(",", ".")
        if p["title"].lower() in cl or str(p["id"]) in claim:
            return True
        if price_str.lower() in cl or str(p["price"]) in claim.replace(".", "").replace("$", ""):
            return True
    for order in MOCK_ORDERS.values():
        if order["name"] in claim or str(order["id"]) in claim:
            return True
        if order["total_price"].replace(".", "") in claim.replace(".", "").replace("$", "").replace(" cop", ""):
            return True
    # Claims verificables: ignorar números de teléfono y IDs cortos
    if re.match(r"^\+?\d{10,}$", claim.replace(" ", "")):
        return True
    if claim.startswith("#"):
        return claim in MOCK_ORDERS or any(o["name"] == claim for o in MOCK_ORDERS.values())
    return False


async def evaluate_hallucination(response: str, llm: Any | None = None) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    use_llm = llm is not None or (api_key and not api_key.startswith("test"))

    if use_llm and llm is None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_MODEL", "gemini-1.5-pro"),
            google_api_key=api_key,
            temperature=0.0,
        )
        claims = await _extract_claims_llm(response, llm)
    else:
        claims = _extract_claims_heuristic(response)

    if not claims:
        return {"hallucinated_claims": [], "hallucination_rate": 0.0, "claims_checked": 0, "passed": True}

    hallucinated = [c for c in claims if not _verify_claim(c)]
    rate = len(hallucinated) / len(claims) if claims else 0.0

    return {
        "hallucinated_claims": hallucinated,
        "hallucination_rate": round(rate, 3),
        "claims_checked": len(claims),
        "passed": rate == 0.0,
    }
