"""LLM-as-judge con Gemini para calidad de respuesta."""

from __future__ import annotations

import json
import os
import re
from typing import Any

JUDGE_PROMPT = """Eres un evaluador experto en atención al cliente de e-commerce.
Evalúa la siguiente respuesta según estos criterios:
1. RESOLUCIÓN (0-3): ¿Resuelve completamente la consulta del usuario?
2. PRECISIÓN (0-3): ¿La información es correcta y específica?
3. TONO (0-2): ¿Es amable y apropiado para WhatsApp?
4. FORMATO (0-2): ¿Usa formato WhatsApp correctamente (*negrita*, listas)?

Consulta: {query}
Criterio específico: {judge_criteria}
Respuesta a evaluar: {response}

Responde SOLO con JSON: {{"scores": {{"resolucion": N, "precision": N, "tono": N, "formato": N}}, "total": N, "feedback": "..."}}"""

PASS_THRESHOLD = 7.0
MAX_SCORE = 10.0


def _heuristic_judge(query: str, response: str, criteria: str, must_contain: list[str], must_not_contain: list[str]) -> dict:
    """Fallback offline cuando no hay Gemini."""
    score = 5.0
    feedback_parts = []

    if not response or len(response.strip()) < 5:
        return {"scores": {"resolucion": 0, "precision": 0, "tono": 0, "formato": 0}, "total": 0, "feedback": "Respuesta vacía"}

    rl = response.lower()
    for term in must_contain:
        if term.lower() in rl:
            score += 0.8
        else:
            feedback_parts.append(f"Falta mencionar '{term}'")

    for term in must_not_contain:
        if term.lower() in rl:
            score -= 1.5
            feedback_parts.append(f"No debería contener '{term}'")

    if "*" in response:
        score += 0.5
    if any(w in rl for w in ("hola", "gracias", "lamento", "con gusto")):
        score += 0.5

    total = min(MAX_SCORE, max(0, round(score, 1)))
    return {
        "scores": {
            "resolucion": min(3, int(total / 3.5)),
            "precision": min(3, int(total / 3.5)),
            "tono": min(2, int(total / 5)),
            "formato": 2 if "*" in response else 1,
        },
        "total": total,
        "feedback": "; ".join(feedback_parts) or "Evaluación heurística offline.",
        "mode": "heuristic",
    }


async def evaluate_response(
    query: str,
    response: str,
    judge_criteria: str,
    must_contain: list[str] | None = None,
    must_not_contain: list[str] | None = None,
    llm: Any | None = None,
) -> dict:
    must_contain = must_contain or []
    must_not_contain = must_not_contain or []

    api_key = os.environ.get("GEMINI_API_KEY", "")
    use_gemini = llm is not None or (api_key and not api_key.startswith("test"))

    if not use_gemini:
        result = _heuristic_judge(query, response, judge_criteria, must_contain, must_not_contain)
        result["passed"] = result["total"] >= PASS_THRESHOLD
        return result

    if llm is None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_MODEL", "gemini-1.5-pro"),
            google_api_key=api_key,
            temperature=0.0,
        )

    prompt = JUDGE_PROMPT.format(
        query=query,
        judge_criteria=judge_criteria,
        response=response[:3000],
    )
    msg = await llm.ainvoke(prompt)
    raw = msg.content if hasattr(msg, "content") else str(msg)

    try:
        if "```" in raw:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            raw = m.group(0) if m else raw
        parsed = json.loads(raw)
        total = float(parsed.get("total", 0))
        if "total" not in parsed and "scores" in parsed:
            total = sum(parsed["scores"].values())
            parsed["total"] = total
    except (json.JSONDecodeError, TypeError):
        parsed = _heuristic_judge(query, response, judge_criteria, must_contain, must_not_contain)

    parsed["passed"] = float(parsed.get("total", 0)) >= PASS_THRESHOLD
    parsed["mode"] = "gemini"
    return parsed
