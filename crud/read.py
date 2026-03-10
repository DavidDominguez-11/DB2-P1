"""
crud/read.py — Parametric Grill Hub
READ operations (15 pts):
  1. historial_usuario_paginado()  — find + sort + skip + limit + $lookup
  2. detalle_orden_completo()      — $lookup: ordenes→usuarios→restaurantes→menu_items
  3. restaurantes_cercanos()       — $near + 2dsphere
  4. busqueda_texto_menu()         — $text + $meta textScore
  5. consulta_filtros_proyecciones() — filtros + proyecciones + ordenamiento + skip + limit + $lookup
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from config import get_db


# ──────────────────────────────────────────────────────────────────────────────
# 1. Historial usuario paginado
# ──────────────────────────────────────────────────────────────────────────────

def historial_usuario_paginado(db, usuario_id: ObjectId,
                                pagina: int = 1, por_pagina: int = 10) -> dict:
    """
    Retorna órdenes del usuario paginadas, enriquecidas con datos del restaurante.
    Usa find + sort + skip + limit + $lookup.
    """
    skip = (pagina - 1) * por_pagina

    # Consulta paginada básica
    cursor = db.ordenes.find(
        {"usuario_id": usuario_id}
    ).sort(
        "fecha_creacion", DESCENDING
    ).skip(skip).limit(por_pagina)

    ordenes = list(cursor)

    # Enriquecer con datos del restaurante via pipeline
    pipeline = [
        {"$match": {"usuario_id": usuario_id}},
        {"$sort":  {"fecha_creacion": DESCENDING}},
        {"$skip":  skip},
        {"$limit": por_pagina},
        {"$lookup": {
            "from":         "restaurantes",
            "localField":   "restaurante_id",
            "foreignField": "_id",
            "as":           "restaurante"
        }},
        {"$unwind": {"path": "$restaurante", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id":             1,
            "estado":          1,
            "total":           1,
            "fecha_creacion":  1,
            "items":           1,
            "restaurante_nombre": "$restaurante.nombre",
            "restaurante_id":  1
        }}
    ]

    ordenes_enriquecidas = list(db.ordenes.aggregate(pipeline))
    total = db.ordenes.count_documents({"usuario_id": usuario_id})

    return {
        "ordenes":    ordenes_enriquecidas,
        "total":      total,
        "pagina":     pagina,
        "por_pagina": por_pagina,
        "paginas":    (total + por_pagina - 1) // por_pagina
    }


# ──────────────────────────────────────────────────────────────────────────────
# 2. Detalle de orden completo — multi-lookup
# ──────────────────────────────────────────────────────────────────────────────

def detalle_orden_completo(db, orden_id: ObjectId) -> dict | None:
    """
    Retorna la orden completa con:
    ordenes → usuarios → restaurantes → menu_items (por cada item)
    """
    pipeline = [
        {"$match": {"_id": orden_id}},

        # Lookup usuario
        {"$lookup": {
            "from":         "usuarios",
            "localField":   "usuario_id",
            "foreignField": "_id",
            "as":           "usuario"
        }},
        {"$unwind": {"path": "$usuario", "preserveNullAndEmptyArrays": True}},

        # Lookup restaurante
        {"$lookup": {
            "from":         "restaurantes",
            "localField":   "restaurante_id",
            "foreignField": "_id",
            "as":           "restaurante"
        }},
        {"$unwind": {"path": "$restaurante", "preserveNullAndEmptyArrays": True}},

        # Lookup menu_items (por cada item del array)
        {"$lookup": {
            "from":         "menu_items",
            "localField":   "items.menu_item_id",
            "foreignField": "_id",
            "as":           "menu_detalle"
        }},

        # Proyección final
        {"$project": {
            "_id":               1,
            "estado":            1,
            "total":             1,
            "fecha_creacion":    1,
            "fecha_actualizacion": 1,
            "notas":             1,
            "direccion_entrega": 1,
            "items":             1,
            "usuario_nombre":    {"$concat": ["$usuario.nombre", " ", "$usuario.apellido"]},
            "usuario_email":     "$usuario.email",
            "restaurante_nombre": "$restaurante.nombre",
            "restaurante_ciudad": "$restaurante.ubicacion.ciudad",
            "menu_detalle":      1
        }}
    ]

    resultado = list(db.ordenes.aggregate(pipeline))
    return resultado[0] if resultado else None


# ──────────────────────────────────────────────────────────────────────────────
# 3. Restaurantes cercanos — $near + 2dsphere
# ──────────────────────────────────────────────────────────────────────────────

def restaurantes_cercanos(db, longitud: float, latitud: float,
                           radio_metros: int = 2000,
                           limite: int = 10) -> list:
    """
    Busca restaurantes activos dentro de `radio_metros` usando $near y 2dsphere.
    coordinates = [longitud, latitud] (formato GeoJSON)
    """
    cursor = db.restaurantes.find(
        {
            "activo": True,
            "ubicacion": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [longitud, latitud]
                    },
                    "$maxDistance": radio_metros
                }
            }
        },
        {
            "nombre":                1,
            "categorias":            1,
            "calificacion_promedio": 1,
            "ubicacion.ciudad":      1,
            "telefono":              1
        }
    ).limit(limite)

    return list(cursor)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Búsqueda de texto en menu_items — $text + $meta textScore
# ──────────────────────────────────────────────────────────────────────────────

def busqueda_texto_menu(db, termino: str, limite: int = 10) -> list:
    """
    Busca menu_items por texto en nombre (weight:10) y descripcion (weight:5).
    Ordena por textScore descendente.
    """
    cursor = db.menu_items.find(
        {"$text": {"$search": termino}},
        {"score": {"$meta": "textScore"}}
    ).sort(
        [("score", {"$meta": "textScore"})]
    ).limit(limite)

    return list(cursor)


# ──────────────────────────────────────────────────────────────────────────────
# 5. Consulta con filtros, proyecciones, skip, limit y lookup
# ──────────────────────────────────────────────────────────────────────────────

def consulta_ordenes_filtradas(db, estado: str = None,
                                restaurante_id: ObjectId = None,
                                pagina: int = 1, por_pagina: int = 20,
                                orden_campo: str = "fecha_creacion",
                                orden_dir: int = DESCENDING) -> dict:
    """
    Consulta órdenes con filtros opcionales, proyección, skip, limit y $lookup.
    Usa: filtros + proyecciones + ordenamiento + skip + limit + $lookup.
    """
    filtro = {}
    if estado:
        filtro["estado"] = estado
    if restaurante_id:
        filtro["restaurante_id"] = restaurante_id

    skip = (pagina - 1) * por_pagina

    pipeline = [
        {"$match": filtro},
        {"$sort":  {orden_campo: orden_dir}},
        {"$skip":  skip},
        {"$limit": por_pagina},

        # $lookup restaurante
        {"$lookup": {
            "from":         "restaurantes",
            "localField":   "restaurante_id",
            "foreignField": "_id",
            "as":           "restaurante"
        }},
        {"$unwind": {"path": "$restaurante", "preserveNullAndEmptyArrays": True}},

        # $lookup usuario
        {"$lookup": {
            "from":         "usuarios",
            "localField":   "usuario_id",
            "foreignField": "_id",
            "as":           "usuario"
        }},
        {"$unwind": {"path": "$usuario", "preserveNullAndEmptyArrays": True}},

        # Proyección — solo campos necesarios
        {"$project": {
            "_id":               1,
            "estado":            1,
            "total":             1,
            "fecha_creacion":    1,
            "items_count":       {"$size": "$items"},
            "restaurante_nombre": "$restaurante.nombre",
            "usuario_nombre":    "$usuario.nombre"
        }}
    ]

    resultados = list(db.ordenes.aggregate(pipeline))
    total = db.ordenes.count_documents(filtro)

    return {
        "resultados":  resultados,
        "total":       total,
        "pagina":      pagina,
        "por_pagina":  por_pagina,
        "filtros":     filtro
    }


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades adicionales
# ──────────────────────────────────────────────────────────────────────────────

def obtener_restaurante(db, restaurante_id: ObjectId) -> dict | None:
    return db.restaurantes.find_one({"_id": restaurante_id})

def obtener_usuario(db, usuario_id: ObjectId) -> dict | None:
    return db.usuarios.find_one({"_id": usuario_id})

def obtener_orden(db, orden_id: ObjectId) -> dict | None:
    return db.ordenes.find_one({"_id": orden_id})

def listar_restaurantes(db, filtro_estado: str = "activos", limite: int = 50) -> list:
    """
    Lista restaurantes con filtro de estado: 'activos', 'inactivos' o 'todos'.
    """
    if filtro_estado == "activos":
        filtro = {"activo": True}
    elif filtro_estado == "inactivos":
        filtro = {"activo": False}
    else:
        filtro = {}
    return list(db.restaurantes.find(filtro).limit(limite))

def listar_menu_restaurante(db, restaurante_id: ObjectId,
                             solo_disponibles: bool = True) -> list:
    filtro = {"restaurante_id": restaurante_id}
    if solo_disponibles:
        filtro["disponible"] = True
    return list(db.menu_items.find(filtro))

def listar_usuarios(db, solo_activos: bool = True, limite: int = 50) -> list:
    filtro = {"activo": True} if solo_activos else {}
    return list(db.usuarios.find(filtro).limit(limite))
