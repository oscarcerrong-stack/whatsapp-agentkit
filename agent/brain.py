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


async def extraer_producto_principal(mensaje_usuario: str, respuesta: str) -> str | None:
    """
    Extrae el nombre del producto principal mencionado en el intercambio.
    Retorna None si no se menciona un producto especifico.
    """
    try:
        prompt = f"""Del siguiente intercambio, extrae SOLO el nombre del producto principal mencionado.
Responde UNICAMENTE con el nombre del producto (ej: "Alicate Universal 6" o "Taladro Percutor").
Si hay varios productos, elige el mas relevante.
Si no hay un producto especifico, responde exactamente: NINGUNO

Usuario pregunto: {mensaje_usuario}
Respuesta del agente: {respuesta[:500]}"""

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )
        resultado = response.content[0].text.strip()
        if resultado.upper() == "NINGUNO" or not resultado:
            return None
        return resultado
    except Exception:
        return None


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
