import os
import logging
from typing import AsyncIterator, TypedDict, Annotated, List, Sequence, cast
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.tools import Tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from app2.agents.prompts import SYSTEM_INSTRUCTION
from app2.database import log_interaction
from langchain_core.messages import trim_messages

from app2.tools.langgraph_tools import (
    get_monthly_sales_summary,
    compare_last_month,
    top_expense_categories,
    explain_variance,
)

logger = logging.getLogger(__name__)

TOOLS = cast(
    Sequence[Tool],
    [
        get_monthly_sales_summary,
        compare_last_month,
        top_expense_categories,
        explain_variance,
    ],
)

def make_llm():
    """
    Supuesto explícito:
    - Usás LangChain wrappers para el proveedor.
    - Elegís por env sin cambiar código.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))

    if provider == "gemini":
        return ChatGoogleGenerativeAI(model=model, temperature=temperature)

    raise ValueError(f"Unsupported LLM_PROVIDER={provider}")

# Configuramos el "trimmer"
# Mantendrá los últimos 10 mensajes, pero siempre preservará el SystemMessage inicial
trimmer = trim_messages(
    max_tokens=2000, # Aproximación rápida o usa un contador de tokens real
    strategy="last",
    token_counter=len, # En este caso contamos cantidad de mensajes para simplificar
    include_system=True,
    allow_partial=False,
    start_on="human",
)


def build_graph():
    llm = make_llm().bind_tools(TOOLS)

    async def agent_llm(state: AgentState):
        # El historial completo de 'messages' ya viene en el state
        # gracias a Annotated[List[BaseMessage], add_messages]
        # Aplicamos el recorte antes de invocar al modelo
        # Esto evita que el contexto crezca hasta el infinito
        trimmed_messages = trimmer.invoke(state["messages"])
        resp = await llm.ainvoke(trimmed_messages)
        return {"messages": [resp]}

    tool_node = ToolNode(TOOLS)

    g = StateGraph(AgentState)
    g.add_node("agent_llm", agent_llm)
    g.add_node("tools", tool_node)

    g.set_entry_point("agent_llm")
    g.add_conditional_edges("agent_llm", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "agent_llm")

    # CRÍTICO: Compilar con checkpointer para habilitar hilos de conversación
    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

class LangGraphAgentRuntime:
    def __init__(self):
        self.graph = build_graph()
        # Configuración inicial: ID de chat y ruta de DB
        self.config = {
            "configurable": {
                "thread_id": "single_pyme_user", # Cambiar por ID dinámico para multi-usuario
                "db_path": "business.db"
            }
        }

    async def start_session(self):
        # Mantengo API compatible con main.py
        logger.info("Sesión de agente iniciada.")
        return

    async def stop(self):
        logger.info("Sesión de agente finalizada.")
        return

    async def respond_stream(self, message: str) -> AsyncIterator[str]:
            # Solo enviamos el mensaje nuevo. El SystemMessage se maneja con lógica de inicio.
            current_state = await self.graph.aget_state(self.config)
            
            inputs = []
            # Si es la primera vez (historial vacío), inyectamos la instrucción de sistema
            if not current_state.values.get("messages"):
                inputs.append(SystemMessage(content=SYSTEM_INSTRUCTION))
            
            inputs.append(HumanMessage(content=message))
            full_response = [] # Para acumular la respuesta y guardarla al final
        
            async for event in self.graph.astream_events(
                {"messages": inputs}, 
                config=self.config, 
                version="v2"
            ):
                if event.get("event") == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content"):
                        content = chunk.content
                        full_response.append(content)
                        yield content

                # Al finalizar el stream, guardamos en la DB
            response_text = "".join(full_response)
            thread_id = self.config["configurable"].get("thread_id", "unknown")
            
            # Lo hacemos de forma asíncrona para no bloquear el cierre del socket
            try:
                log_interaction(message, response_text, thread_id)
            except Exception as e:
                logger.error(f"Error al guardar log de auditoría: {e}")
            
            yield "__END__"


'''
2. ¿Cómo expandirlo a "Multi-usuario" en el futuro?
Expandir esto a múltiples usuarios es relativamente sencillo gracias a la arquitectura de LangGraph. Los cambios serían en tres niveles:

A. Identificación en el Frontend/API
En lugar de un thread_id fijo ("pyme_user_01"), el main.py debería recibir un ID de sesión (por ejemplo, desde un token JWT o una cookie) y pasarlo al método respond_stream.

B. Persistencia Externa (Base de Datos)
El MemorySaver guarda todo en la memoria RAM del proceso. Si el servidor se reinicia, todos los usuarios pierden su historial. Para multi-usuario real, deberías cambiarlo por:

PostgresSaver: Para persistencia en base de datos relacional.

RedisSaver: Para una gestión de sesiones rápida y con expiración.

C. Aislamiento de Estados
LangGraph se encarga de que el state del thread_id="usuario_A" sea totalmente invisible para el thread_id="usuario_B". No hay riesgo de que la IA confunda los números de una PYME con otra si los IDs están bien gestionados.

3. Falencia Detectada: El "System Instruction" duplicado
En tu código actual (runtime.py y langgraph_runtime.py), estás enviando el SystemMessage en cada mensaje del usuario.

Riesgo: Esto infla el consumo de tokens innecesariamente y puede confundir al modelo si el historial crece.

Mejora: El SystemMessage debe enviarse solo la primera vez o, mejor aún, definirse como un mensaje estático en el primer nodo del grafo si el estado está vacío.'''