# agent/tools.py — Herramientas del agente DISUR
# Generado por AgentKit

import os
import yaml
import logging

logger = logging.getLogger("agentkit")


def cargar_info_negocio() -> dict:
    """Carga la informacion del negocio desde business.yaml."""
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    """Retorna el horario de atencion de DISUR."""
    info = cargar_info_negocio()
    return {
        "horario": info.get("negocio", {}).get("horario", "No disponible"),
        "esta_abierto": True,
    }


def buscar_en_knowledge(consulta: str) -> str:
    """
    Busca informacion relevante en los archivos de /knowledge.
    Util para consultas sobre productos o precios especificos.
    """
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        if not archivo.endswith(".txt"):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                if consulta.lower() in contenido.lower():
                    lineas_relevantes = [
                        linea for linea in contenido.split("\n")
                        if consulta.lower() in linea.lower()
                    ]
                    resultados.extend(lineas_relevantes[:10])
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n".join(resultados)
    return "No encontre informacion especifica sobre ese producto en el catalogo."
