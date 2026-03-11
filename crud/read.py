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

# ──────────────────────────────────────────────────────────────────────────────
# CONSULTAS AVANZADAS (REQUERIMIENTO SECCIÓN 4.2)
# ──────────────────────────────────────────────────────────────────────────────

def reporte_resenas_enriquecido(db, min_calificacion: int = 3, tag: str = None, 
                                pagina: int = 1, por_pagina: int = 10) -> list:
    """
    REPORTE 1: Reseñas -> Usuarios -> Restaurantes -> Órdenes
    Cumple con: Filtros, 3 Lookups (uno correlacionado), Proyecciones, Ordenamiento, Skip/Limit.
    """
    skip = (pagina - 1) * por_pagina
    filtro = {"calificacion": {"$gte": min_calificacion}}
    if tag:
        filtro["tags"] = tag

    pipeline = [
        {"$match": filtro},
        
        # Lookup 1: Usuarios (para nombre)
        {"$lookup": {
            "from": "usuarios",
            "localField": "usuario_id",
            "foreignField": "_id",
            "as": "user"
        }},
        {"$unwind": "$user"},

        # Lookup 2: Restaurantes (para nombre y ciudad)
        {"$lookup": {
            "from": "restaurantes",
            "localField": "restaurante_id",
            "foreignField": "_id",
            "as": "rest"
        }},
        {"$unwind": "$rest"},

        # Lookup 3 (Correlacionado): Buscar la última orden entregada de ese usuario en ese restaurante
        {"$lookup": {
            "from": "ordenes",
            "let": {"u_id": "$usuario_id", "r_id": "$restaurante_id"},
            "pipeline": [
                {"$match": {
                    "$expr": {
                        "$and": [
                            {"$eq": ["$usuario_id", "$$u_id"]},
                            {"$eq": ["$restaurante_id", "$$r_id"]},
                            {"$eq": ["$estado", "entregado"]}
                        ]
                    }
                }},
                {"$sort": {"fecha_creacion": -1}},
                {"$limit": 1},
                {"$project": {"total": 1, "fecha_creacion": 1}}
            ],
            "as": "ultima_orden"
        }},

        # Ordenamiento Doble
        {"$sort": {"calificacion": -1, "fecha": -1}},
        
        # Paginación
        {"$skip": skip},
        {"$limit": por_pagina},

        # Proyección Avanzada
        {"$project": {
            "_id": 0,
            "comentario": 1,
            "calificacion": 1,
            "autor": {"$concat": ["$user.nombre", " ", "$user.apellido"]},
            "restaurante": "$rest.nombre",
            "ciudad": "$rest.ubicacion.ciudad",
            "monto_orden": {"$arrayElemAt": ["$ultima_orden.total", 0]},
            "fecha_reseña": "$fecha"
        }}
    ]
    return list(db.resenas.aggregate(pipeline))

def ranking_popularidad_menu(db, categoria: str = None, min_precio: float = 0, 
                             max_precio: float = 1000, pagina: int = 1, por_pagina: int = 10) -> list:
    """
    REPORTE 2: Menu_items -> Restaurantes -> Órdenes
    Analiza la popularidad de platos activos cruzando con el conteo real en órdenes entregadas.
    """
    skip = (pagina - 1) * por_pagina
    filtro = {
        "disponible": True,
        "precio": {"$gte": min_precio, "$lte": max_precio}
    }
    if categoria:
        filtro["categorias"] = categoria

    pipeline = [
        {"$match": filtro},

        # Lookup 1: Restaurante dueño
        {"$lookup": {
            "from": "restaurantes",
            "localField": "restaurante_id",
            "foreignField": "_id",
            "as": "rest"
        }},
        {"$unwind": "$rest"},

        # Lookup 2 (Analítico): Contar en cuántas órdenes ENTREGADAS aparece este plato
        {"$lookup": {
            "from": "ordenes",
            "let": {"item_id": "$_id"},
            "pipeline": [
                {"$match": {
                    "$expr": {"$in": ["$$item_id", "$items.menu_item_id"]},
                    "estado": "entregado"
                }},
                {"$count": "conteo"}
            ],
            "as": "stats"
        }},

        # Ordenamiento por ventas acumuladas
        {"$sort": {"ventas_total": -1}},

        # Paginación
        {"$skip": skip},
        {"$limit": por_pagina},

        # Proyección
        {"$project": {
            "_id": 0,
            "platillo": "$nombre",
            "precio": 1,
            "restaurante": "$rest.nombre",
            "ventas_historicas": "$ventas_total",
            "ordenes_recientes": {"$ifNull": [{"$arrayElemAt": ["$stats.conteo", 0]}, 0]}
        }}
    ]
    return list(db.menu_items.aggregate(pipeline))
