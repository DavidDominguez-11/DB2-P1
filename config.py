"""
config.py — Parametric Grill Hub
Configuración de conexión a MongoDB Atlas.
Cargar MONGO_URI desde variable de entorno o archivo .env
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
import gridfs

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME   = os.getenv("DB_NAME", "parametric_grill_hub")

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Devuelve el cliente MongoClient (singleton)."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_db():
    """Devuelve el objeto de base de datos."""
    return get_client()[DB_NAME]


def get_gridfs():
    """Devuelve el objeto GridFS para almacenamiento de archivos binarios."""
    db = get_db()
    return gridfs.GridFS(db)


# Nombres de colecciones (no modificar)
COL_RESTAURANTES = "restaurantes"
COL_USUARIOS     = "usuarios"
COL_MENU_ITEMS   = "menu_items"
COL_ORDENES      = "ordenes"
COL_RESENAS      = "resenas"

# Estados de orden (enum)
ESTADOS_ORDEN = [
    "pendiente",
    "confirmado",
    "en_preparacion",
    "en_camino",
    "entregado",
    "cancelado",
]
