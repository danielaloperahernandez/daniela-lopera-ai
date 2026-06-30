"""
Estado compartido del grafo LangGraph.
Todos los nodos leen y escriben sobre este TypedDict.
"""

from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ConversationState(TypedDict):
    """Estado de una conversación de WhatsApp atravesando el enjambre de agentes."""

    # Historial completo de la conversación (se acumula con add_messages)
    messages: Annotated[List[BaseMessage], add_messages]

    # Número WhatsApp del usuario (formato E.164, ej: +573001234567)
    phone: str

    # Intención clasificada por classify_intent
    intent: str

    # ID del cliente en Shopify, si se identificó en la sesión
    shopify_customer_id: str

    # Contador de intentos fallidos del validador (máx. 2 antes de escalar)
    attempts: int

    # Flag: el caso requiere intervención humana
    requires_human: bool

    # Respuesta final que se enviará por WhatsApp
    final_response: str

    # ID del mensaje WhatsApp entrante (idempotencia)
    message_id: str

    # Indica si orders_node debe derivar a refunds_node
    needs_refund: bool
