"""Factory de agentes ReAct con Gemini y herramientas LangChain."""

from typing import Sequence

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings


def create_llm() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.2,
    )


def _build_agent(llm, tools, system_prompt: str):
    from langchain.agents import create_agent as build_react_agent

    return build_react_agent(llm, tools, system_prompt=system_prompt)


def create_agent(tools: Sequence[BaseTool], system_prompt: str):
    """
    Crea un agente ReAct con Gemini y las tools indicadas.
    """
    llm = create_llm()
    agent = _build_agent(llm, tools, system_prompt)

    async def invoke_agent(user_message: str) -> str:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=user_message)]}
        )
        last = result["messages"][-1]
        return last.content if hasattr(last, "content") else str(last)

    return invoke_agent
