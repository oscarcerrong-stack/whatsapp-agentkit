# agent/providers/zapi.py — Adaptador para Z-API WhatsApp
# Generado por AgentKit

import os
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")


class ProveedorZapi(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando Z-API (zapi.io)."""

    def __init__(self):
        self.instance_id = os.getenv("ZAPI_INSTANCE_ID")
        self.token = os.getenv("ZAPI_TOKEN")
        self.client_token = os.getenv("ZAPI_CLIENT_TOKEN", "")
        self.base_url = f"https://api.z-api.io/instances/{self.instance_id}/token/{self.token}"

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """Parsea el payload JSON de Z-API."""
        try:
            body = await request.json()
        except Exception:
            return []

        # Ignorar mensajes propios o que no sean texto
        if body.get("fromMe", False):
            return []

        tipo = body.get("type", "")
        if tipo not in ("ReceivedCallback",):
            return []

        # Extraer texto del mensaje
        texto = ""
        if "text" in body:
            texto = body["text"].get("message", "")
        elif "image" in body:
            texto = body["image"].get("caption", "")

        if not texto:
            return []

        telefono = body.get("phone", "")
        mensaje_id = body.get("messageId", "")

        return [MensajeEntrante(
            telefono=telefono,
            texto=texto,
            mensaje_id=mensaje_id,
            es_propio=False,
        )]

    async def enviar_imagen(self, telefono: str, url_imagen: str, caption: str = "") -> bool:
        """Envia imagen via Z-API con texto opcional."""
        if not self.instance_id or not self.token:
            return False

        url = f"{self.base_url}/send-image"
        headers = {"Content-Type": "application/json"}
        if self.client_token:
            headers["Client-Token"] = self.client_token

        payload = {
            "phone": telefono,
            "image": url_imagen,
            "caption": caption,
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code not in (200, 201):
                logger.error(f"Error Z-API imagen: {r.status_code} — {r.text}")
            return r.status_code in (200, 201)

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Envia mensaje de texto via Z-API."""
        if not self.instance_id or not self.token:
            logger.warning("ZAPI_INSTANCE_ID o ZAPI_TOKEN no configurados")
            return False

        url = f"{self.base_url}/send-text"
        headers = {"Content-Type": "application/json"}
        if self.client_token:
            headers["Client-Token"] = self.client_token

        payload = {
            "phone": telefono,
            "message": mensaje,
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code not in (200, 201):
                logger.error(f"Error Z-API: {r.status_code} — {r.text}")
            return r.status_code in (200, 201)
