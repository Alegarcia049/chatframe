import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app2.agents.langgraph_runtime import LangGraphAgentRuntime
from app2.api.v1.meta_webhook import router as meta_webhook_router
from app2.database import init_db
from app2.db.audit import ensure_schema
from app2.db.session import close_pool
from app2.llm.factory import UnsupportedProviderError
from app2.seed import seed_data
from app2.settings import settings

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Agent state (lazy init)
agent: Optional[LangGraphAgentRuntime] = None
agent_ready: bool = False
agent_not_ready_reason: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Maneja el ciclo de vida de la aplicación: Inicio y Cierre."""
    global agent, agent_ready, agent_not_ready_reason

    logger.info("🚀 Iniciando backend del Asistente de Negocio...")

    # Inicialización de DB (solo para desarrollo/demo)
    try:
        init_db()
        seed_data()
        logger.info("✅ Base de datos inicializada y con datos de semilla.")
    except Exception as e:
        logger.error("❌ Error al inicializar la base de datos: %s", e)

    # Bootstrap best-effort de auditoría PostgreSQL
    try:
        await ensure_schema()
        logger.info("✅ Auditoría PostgreSQL lista.")
    except Exception as e:
        logger.error("⚠️ Auditoría PostgreSQL no disponible (best-effort): %s", e)

    # Inicialización lazy del agente (evita crash en import-time)
    try:
        agent = LangGraphAgentRuntime()
        await agent.start_session()
        agent_ready = True
        agent_not_ready_reason = None
        logger.info("✅ Agente listo.")
    except UnsupportedProviderError as e:
        agent = None
        agent_ready = False
        agent_not_ready_reason = str(e)
        logger.error("❌ Agente no disponible por provider no soportado: %s", e)
    except Exception as e:
        agent = None
        agent_ready = False
        agent_not_ready_reason = str(e)
        logger.error("❌ Agente no disponible por error de inicialización: %s", e)

    yield

    # Shutdown
    if agent is not None:
        try:
            await agent.stop()
        except Exception as e:
            logger.error("⚠️ Error deteniendo agente: %s", e)

    try:
        await close_pool()
    except Exception as e:
        logger.error("⚠️ Error cerrando pool de auditoría: %s", e)

    logger.info("🛑 Apagando backend...")


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.include_router(meta_webhook_router, prefix="/api/v1")

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health
@app.get("/health")
def health_check():
    if agent_ready:
        return {"status": "ok", "agent": "ready", "reason": None}
    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "agent": "not_ready", "reason": agent_not_ready_reason},
    )


# WebSocket
@app.websocket("/ws/chat")
async def chat_stream(ws: WebSocket):
    global agent, agent_ready

    if not agent_ready or agent is None:
        denial_fn = getattr(ws, "send_denial_response", None)
        if callable(denial_fn):
            await denial_fn(JSONResponse(status_code=503, content={"detail": "Agent not ready"}))
            return
        await ws.close(code=1013, reason="agent_not_ready")
        return

    await ws.accept()

    # sender_id estable por conexión: query param o uuid
    sender_id = (ws.query_params.get("sender_id") or "").strip() or str(uuid.uuid4())
    platform = "web"

    client_id = id(ws)
    logger.info("🔌 WS connected client_id=%s sender_id=%s platform=%s", client_id, sender_id, platform)

    try:
        while True:
            user_message = await ws.receive_text()
            if not user_message.strip():
                continue

            logger.info("📩 WS message client_id=%s sender_id=%s len=%s", client_id, sender_id, len(user_message))

            try:
                async for chunk in agent.respond_stream(user_message, sender_id=sender_id, platform=platform):
                    await ws.send_text(chunk)
                await ws.send_text("__END__")
            except Exception as stream_err:
                logger.error("❌ Error durante el streaming: %s", stream_err)
                await ws.send_text("Lo siento, ocurrió un error procesando tu solicitud.")
                await ws.send_text("__END__")

    except WebSocketDisconnect:
        logger.info("🔌 WS disconnected client_id=%s sender_id=%s", client_id, sender_id)
    except Exception as e:
        logger.error("⚠️ Error inesperado en WS client_id=%s: %s", client_id, e)
    finally:
        try:
            await ws.close()
        except Exception:
            pass


# Front-end
@app.get("/")
async def read_index():
    return FileResponse("index.html")


app.mount("/static", StaticFiles(directory=".", html=True), name="frontend")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
