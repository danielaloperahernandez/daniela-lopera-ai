"""
Funciones de routing condicional (edges) del grafo LangGraph.
Cada función retorna el nombre del siguiente nodo como string.
"""

from graph.state import ConversationState

MAX_VALIDATION_ATTEMPTS = 2


def route_after_classify(state: ConversationState) -> str:
    """
    Edge condicional: classify_intent → nodo especializado.
    Mapea la intención clasificada al nodo correspondiente.
    """
    intent = state.get("intent", "rag")

    routing = {
        "saludo": "saludo_directo",
        "rag": "rag_node",
        "ventas": "sales_node",
        "pedidos": "orders_node",
        "clientes": "customers_node",
        "escalada": "escalation_node",
        "devolucion": "orders_node",
    }
    return routing.get(intent, "rag_node")


def route_after_orders(state: ConversationState) -> str:
    """
    Edge condicional: orders_node → refunds_node si menciona devolución/reembolso,
    de lo contrario va directo al validador.
    """
    if state.get("needs_refund"):
        return "refunds_node"
    return "response_validator"


def route_after_validator(state: ConversationState) -> str:
    """
    Edge condicional post-validación:
    - attempts >= 2 → escalada forzada
    - attempts > 0 y última validación falló → re-clasificar (reintento)
    - OK → formatear respuesta
    """
    attempts = state.get("attempts", 0)

    if attempts >= MAX_VALIDATION_ATTEMPTS:
        return "escalation_node"

    # Si hubo intentos fallidos pero aún no llegamos al máximo, reintentar
    if attempts > 0:
        # Comprobar si la respuesta actual parece válida (attempts se incrementó
        # en el validador solo si falló; si no incrementó, attempts sigue en 0)
        return "classify_intent"

    return "format_response"


# route_after_saludo y route_after_escalation se resuelven con edges fijos en builder.py
