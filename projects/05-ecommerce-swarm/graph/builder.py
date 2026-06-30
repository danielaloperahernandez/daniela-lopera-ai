"""
Construye y compila el StateGraph de LangGraph.
Ensambla nodos, edges fijos y edges condicionales del enjambre.
"""

from langgraph.graph import END, StateGraph

from graph.edges import (
    route_after_classify,
    route_after_orders,
    route_after_validator,
)
from graph.nodes import (
    classify_intent,
    customers_node,
    escalation_node,
    format_response,
    orders_node,
    rag_node,
    refunds_node,
    response_validator,
    saludo_directo,
    sales_node,
)
from graph.state import ConversationState

_compiled_graph = None


def build_graph() -> StateGraph:
    """
    Construye el grafo de agentes sin compilar.
    Flujo principal:
      START → classify_intent → [nodo especializado] → response_validator
            → format_response → END
    Ramas especiales:
      - orders_node → refunds_node (si needs_refund)
      - saludo_directo / escalation_node → format_response (sin validador)
      - response_validator → classify_intent (reintento) | escalation_node (≥2 intentos)
    """
    graph = StateGraph(ConversationState)

    # Registrar nodos
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("rag_node", rag_node)
    graph.add_node("sales_node", sales_node)
    graph.add_node("orders_node", orders_node)
    graph.add_node("customers_node", customers_node)
    graph.add_node("refunds_node", refunds_node)
    graph.add_node("escalation_node", escalation_node)
    graph.add_node("saludo_directo", saludo_directo)
    graph.add_node("response_validator", response_validator)
    graph.add_node("format_response", format_response)

    # Punto de entrada: siempre clasificar primero
    graph.set_entry_point("classify_intent")

    # classify_intent → nodo especializado según intención
    graph.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "rag_node": "rag_node",
            "sales_node": "sales_node",
            "orders_node": "orders_node",
            "customers_node": "customers_node",
            "escalation_node": "escalation_node",
            "saludo_directo": "saludo_directo",
        },
    )

    # Nodos especializados → validador (excepto saludo y escalada directa)
    for node in ("rag_node", "sales_node", "customers_node", "refunds_node"):
        graph.add_edge(node, "response_validator")

    # orders_node: puede derivar a refunds o al validador
    graph.add_conditional_edges(
        "orders_node",
        route_after_orders,
        {
            "refunds_node": "refunds_node",
            "response_validator": "response_validator",
        },
    )

    # Saludo y escalada → formateo directo (sin pasar por validador)
    graph.add_edge("saludo_directo", "format_response")
    graph.add_edge("escalation_node", "format_response")

    # Validador → reintento, escalada o formateo
    graph.add_conditional_edges(
        "response_validator",
        route_after_validator,
        {
            "format_response": "format_response",
            "classify_intent": "classify_intent",
            "escalation_node": "escalation_node",
        },
    )

    graph.add_edge("format_response", END)

    return graph


def get_compiled_graph():
    """Retorna el grafo compilado (singleton para reutilizar en FastAPI)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph
