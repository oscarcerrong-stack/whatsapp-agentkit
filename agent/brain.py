# agent/brain.py — Cerebro del agente: conexion con Claude API
# Generado por AgentKit

import os
import yaml
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def cargar_config_prompts() -> dict:
    """Lee toda la configuracion desde config/prompts.yaml."""
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def cargar_system_prompt() -> str:
    """Lee el system prompt desde config/prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("system_prompt", "Eres un asistente util. Responde en espanol.")


def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas tecnicos. Por favor intenta de nuevo en unos minutos.")


def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpa, no entendi tu mensaje. ¿Podrias reformularlo?")


def extraer_producto_principal(mensaje_usuario: str, respuesta: str) -> str | None:
    """
    Extrae el nombre del producto principal del mensaje del usuario.
    Usa el mensaje directo para buscar la imagen en disurpro.cl.
    """
    import re

    # Palabras a ignorar para limpiar el mensaje
    stopwords = {
        "tienen", "tiene", "hay", "cuanto", "cuesta", "precio", "de", "del",
        "la", "el", "los", "las", "un", "una", "unos", "unas", "y", "o",
        "que", "como", "donde", "cuando", "para", "con", "sin", "por",
        "quiero", "necesito", "busco", "me", "puedes", "podes", "tienes",
        "comprar", "ver", "mostrar", "informacion", "info", "hola", "buenas",
        "buen", "bueno", "favor", "please", "gracias"
    }

    # Limpiar signos de puntuacion y bajar a minusculas
    texto = re.sub(r'[¿?¡!,.:;]', ' ', mensaje_usuario.lower())
    palabras = texto.split()

    # Filtrar stopwords y palabras muy cortas
    palabras_utiles = [p for p in palabras if p not in stopwords and len(p) > 2]

    if not palabras_utiles:
        return None

    # Retornar las primeras 3 palabras utiles como nombre del producto
    return " ".join(palabras_utiles[:3])


async def generar_respuesta(mensaje: str, historial: list[dict]) -> str:
    """
    Genera una respuesta usando Claude API.

    Args:
        mensaje: El mensaje nuevo del usuario
        historial: Lista de mensajes anteriores [{"role": "user/assistant", "content": "..."}]

    Returns:
        La respuesta generada por Claude
    """
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = cargar_system_prompt()

    mensajes = []
    for msg in historial:
        mensajes.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    mensajes.append({
        "role": "user",
        "content": mensaje
    })

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes
        )

        respuesta = response.content[0].text
        logger.info(f"Respuesta generada ({response.usage.input_tokens} in / {response.usage.output_tokens} out)")
        return respuesta

    except Exception as e:
        logger.error(f"Error Claude API: {e}")
        return obtener_mensaje_error()
