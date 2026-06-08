# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta, extraer_producto_principal
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor
from agent.image_search import obtener_imagen_producto

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))

# Cache de mensajes ya procesados para evitar duplicados
_mensajes_procesados: set[str] = set()
_MAX_CACHE = 500


def _ya_procesado(mensaje_id: str) -> bool:
    """Retorna True si el mensaje ya fue procesado (evita duplicados)."""
    if mensaje_id in _mensajes_procesados:
        return True
    _mensajes_procesados.add(mensaje_id)
    if len(_mensajes_procesados) > _MAX_CACHE:
        # Limpiar la mitad mas antigua cuando el cache crece mucho
        items = list(_mensajes_procesados)
        _mensajes_procesados.clear()
        _mensajes_procesados.update(items[_MAX_CACHE // 2:])
    return False


async def procesar_mensaje(telefono: str, texto: str, mensaje_id: str):
    """Procesa un mensaje en background: llama a Claude y responde por WhatsApp."""
    try:
        historial = await obtener_historial(telefono)
        respuesta = await generar_respuesta(texto, historial)

        await guardar_mensaje(telefono, "user", texto)
        await guardar_mensaje(telefono, "assistant", respuesta)

        # Enviar imagen del producto primero si aplica
        if hasattr(proveedor, "enviar_imagen"):
            producto = extraer_producto_principal(texto, respuesta)
            if producto:
                imagen_url = await obtener_imagen_producto(producto)
                if imagen_url:
                    await proveedor.enviar_imagen(telefono, imagen_url)
                    logger.info(f"Imagen enviada para '{producto}': {imagen_url}")

        await proveedor.enviar_mensaje(telefono, respuesta)
        logger.info(f"Respuesta a {telefono}: {respuesta[:100]}")

    except Exception as e:
        logger.error(f"Error procesando mensaje {mensaje_id}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al arrancar el servidor."""
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield


app = FastAPI(
    title="Asistente Disur — DISUR WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "agentkit-disur", "agente": "Asistente Disur"}


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """
    Recibe mensajes de WhatsApp y responde 200 de inmediato.
    El procesamiento ocurre en background para evitar timeouts y mensajes duplicados.
    """
    try:
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            if msg.es_propio or not msg.texto:
                continue

            # Ignorar si ya procesamos este mensaje (Z-API puede reintentar)
            if _ya_procesado(msg.mensaje_id):
                logger.info(f"Mensaje duplicado ignorado: {msg.mensaje_id}")
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")
            background_tasks.add_task(
                procesar_mensaje, msg.telefono, msg.texto, msg.mensaje_id
            )

        # Responder 200 inmediatamente para que Z-API no reintente
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return {"status": "error", "detail": str(e)}
