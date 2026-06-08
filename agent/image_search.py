# agent/image_search.py — Busqueda de imagenes en disurpro.cl
# Generado por AgentKit

import re
import unicodedata
import logging
import httpx

logger = logging.getLogger("agentkit")

TIENDA_URL = "https://www.disurpro.cl"
CDN = "https://dojiw2m9tvv09.cloudfront.net"

_catalogo_cache: list[str] = []


def _cargar_catalogo() -> list[str]:
    """Carga los nombres de productos del catalogo local."""
    global _catalogo_cache
    if _catalogo_cache:
        return _catalogo_cache
    try:
        with open("knowledge/lista_precios_procesada.txt", "r", encoding="utf-8") as f:
            lineas = f.readlines()
        productos = []
        for linea in lineas[5:]:  # saltar encabezados
            partes = linea.strip().split(" | ")
            if len(partes) >= 3:
                productos.append(partes[2].strip())  # nombre del producto
        _catalogo_cache = productos
        return productos
    except Exception:
        return []


def slugificar(texto: str) -> str:
    """Convierte texto a slug URL."""
    # Limpiar artefactos de encoding (ej: Â¨ → nada, Ã → nada)
    texto = re.sub(r'[Â-Ã][^\w\s]?', '', texto)
    texto = re.sub(r'[-ÿ]', '', texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r'[^a-z0-9\s-]', ' ', texto)
    texto = re.sub(r'[\s-]+', '-', texto)
    return texto.strip('-')


def normalizar(texto: str) -> str:
    """Normaliza texto para comparacion: sin tildes, minusculas."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def buscar_mejor_producto(consulta: str) -> str | None:
    """
    Busca el producto mas relevante en el catalogo local.
    Retorna el nombre exacto del producto para generar el slug.
    """
    productos = _cargar_catalogo()
    if not productos:
        return None

    consulta_norm = normalizar(consulta)
    palabras = consulta_norm.split()

    # Coincidencia exacta primero
    for producto in productos:
        if consulta_norm in normalizar(producto):
            return producto

    # Coincidencia por todas las palabras
    for producto in productos:
        prod_norm = normalizar(producto)
        if all(p in prod_norm for p in palabras):
            return producto

    # Coincidencia por la mayoria de palabras (al menos 60%)
    mejor = None
    mejor_score = 0
    for producto in productos:
        prod_norm = normalizar(producto)
        coincidencias = sum(1 for p in palabras if p in prod_norm)
        score = coincidencias / max(len(palabras), 1)
        if score > mejor_score and score >= 0.5:
            mejor_score = score
            mejor = producto

    return mejor


async def _fetch_imagen_desde_pagina(url: str) -> str | None:
    """Obtiene la imagen og:image de una pagina de producto."""
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; AgentKit/1.0)"}
            r = await client.get(url, headers=headers)
            if r.status_code != 200:
                return None
            html = r.text

            # og:image
            match = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
            if not match:
                match = re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', html)
            if match:
                return match.group(1).split('?')[0]

            # Fallback: primera imagen de producto en CDN
            match = re.search(rf'{re.escape(CDN)}/\d+/product/[^"\'>\s]+', html)
            if match:
                return match.group(0).split('?')[0]
    except Exception as e:
        logger.debug(f"Error fetching {url}: {e}")
    return None


async def obtener_imagen_producto(consulta: str) -> str | None:
    """
    Busca la imagen del producto mas relevante para la consulta dada.
    1. Busca el nombre exacto en el catalogo local
    2. Genera el slug y consulta disurpro.cl
    """
    # Buscar nombre exacto en catalogo
    producto_exacto = buscar_mejor_producto(consulta)
    logger.info(f"Consulta: '{consulta}' → Producto en catalogo: '{producto_exacto}'")

    candidatos = []
    if producto_exacto:
        candidatos.append(slugificar(producto_exacto))

    # Tambien intentar con la consulta original
    candidatos.append(slugificar(consulta))

    # Probar cada slug
    for slug in candidatos:
        if not slug:
            continue
        url = f"{TIENDA_URL}/product/{slug}"
        imagen = await _fetch_imagen_desde_pagina(url)
        if imagen:
            logger.info(f"Imagen encontrada: {imagen}")
            return imagen

    logger.info(f"No se encontro imagen para '{consulta}'")
    return None
