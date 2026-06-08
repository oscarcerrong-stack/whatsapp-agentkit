# agent/image_search.py — Busqueda de imagenes en disurpro.cl
# Generado por AgentKit

import re
import unicodedata
import logging
import httpx

logger = logging.getLogger("agentkit")

TIENDA_URL = "https://www.disurpro.cl"


def slugificar(texto: str) -> str:
    """Convierte un nombre de producto a slug para la URL de disurpro.cl."""
    # Normalizar caracteres unicode (quitar tildes)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    # Minusculas
    texto = texto.lower()
    # Reemplazar caracteres especiales por espacio
    texto = re.sub(r'[^a-z0-9\s-]', ' ', texto)
    # Reemplazar espacios multiples y guiones por un solo guion
    texto = re.sub(r'[\s-]+', '-', texto)
    return texto.strip('-')


async def buscar_imagen_producto(nombre_producto: str) -> str | None:
    """
    Busca la imagen principal de un producto en disurpro.cl.
    Retorna la URL de la imagen o None si no la encuentra.
    """
    slug = slugificar(nombre_producto)
    url_producto = f"{TIENDA_URL}/product/{slug}"

    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; AgentKit/1.0)"}
            r = await client.get(url_producto, headers=headers)

            if r.status_code != 200:
                logger.debug(f"Producto no encontrado en {url_producto}: {r.status_code}")
                return None

            html = r.text

            # Buscar og:image (mas confiable)
            match = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
            if not match:
                match = re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', html)

            if match:
                imagen_url = match.group(1)
                # Limpiar el timestamp dinamico para que la URL sea estable
                imagen_url = re.sub(r'\?.*$', '', imagen_url)
                logger.info(f"Imagen encontrada para '{nombre_producto}': {imagen_url}")
                return imagen_url

            # Fallback: buscar imagen de producto en CloudFront
            match = re.search(
                r'https://dojiw2m9tvv09\.cloudfront\.net/\d+/product/[^"\'>\s]+',
                html
            )
            if match:
                return match.group(0).split('?')[0]

    except Exception as e:
        logger.warning(f"Error buscando imagen de '{nombre_producto}': {e}")

    return None


async def buscar_imagen_desde_busqueda(nombre_producto: str) -> str | None:
    """
    Busca el producto en el buscador de disurpro.cl si la URL directa no funciona.
    """
    try:
        search_url = f"{TIENDA_URL}/search?q={nombre_producto.replace(' ', '+')}"
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; AgentKit/1.0)"}
            r = await client.get(search_url, headers=headers)

            if r.status_code != 200:
                return None

            # Buscar primera imagen de producto en los resultados
            match = re.search(
                r'https://dojiw2m9tvv09\.cloudfront\.net/\d+/product/[^"\'>\s]+',
                r.text
            )
            if match:
                return match.group(0).split('?')[0]

    except Exception as e:
        logger.warning(f"Error en busqueda de imagen: {e}")

    return None


async def obtener_imagen_producto(nombre_producto: str) -> str | None:
    """
    Intenta obtener la imagen de un producto probando primero URL directa,
    luego busqueda en el sitio.
    """
    # Intento 1: URL directa con slug
    imagen = await buscar_imagen_producto(nombre_producto)
    if imagen:
        return imagen

    # Intento 2: Busqueda en el sitio
    imagen = await buscar_imagen_desde_busqueda(nombre_producto)
    return imagen
