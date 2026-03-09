"""
crud/create.py — Parametric Grill Hub
CREATE operations:
  1. crear_restaurante() — insertOne + GridFS
  2. crear_usuario()     — insertOne + unique email
  3. crear_menu_item()   — insertOne referenciado
  4. crear_orden()       — transacción multi-doc (proxy a transactions/orders.py)
  5. seed_ordenes()      — BulkWrite 50,000 docs (proxy a scripts/seed.py)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from config import get_db, get_gridfs
from transactions.orders import crear_orden as _crear_orden_tx
from gridfs_utils.files import subir_imagen_restaurante, subir_imagen_menu_item


# ──────────────────────────────────────────────────────────────────────────────
# 1. crear_restaurante
# ──────────────────────────────────────────────────────────────────────────────

def crear_restaurante(db, datos: dict, imagen_bytes: bytes = None,
                       imagen_filename: str = "imagen.jpg") -> ObjectId:
    """
    Inserta un restaurante. Si se proveen imagen_bytes, sube a GridFS.
    JSON Schema valida los campos.
    """
    # Asegurar campos requeridos
    doc = {
        "nombre":                datos["nombre"],
        "descripcion":           datos.get("descripcion", ""),
        "telefono":              datos.get("telefono", ""),
        "email":                 datos.get("email", ""),
        "categorias":            datos["categorias"],
        "horario":               datos.get("horario", {
            "lunes":     {"apertura": "08:00", "cierre": "21:00"},
            "martes":    {"apertura": "08:00", "cierre": "21:00"},
            "miercoles": {"apertura": "08:00", "cierre": "21:00"},
            "jueves":    {"apertura": "08:00", "cierre": "21:00"},
            "viernes":   {"apertura": "08:00", "cierre": "22:00"},
            "sabado":    {"apertura": "09:00", "cierre": "22:00"},
            "domingo":   {"apertura": "10:00", "cierre": "20:00"},
        }),
        "ubicacion":             datos["ubicacion"],
        "calificacion_promedio": float(datos.get("calificacion_promedio", 0.0)),
        "total_resenas":         int(datos.get("total_resenas", 0)),
        "activo":                bool(datos.get("activo", True)),
        "imagen_id":             None,
        "fecha_registro":        datos.get("fecha_registro", datetime.datetime.utcnow())
    }

    result = db.restaurantes.insert_one(doc)
    restaurante_id = result.inserted_id

    # Subir imagen a GridFS si se proporcionó
    if imagen_bytes:
        subir_imagen_restaurante(db, restaurante_id, imagen_bytes, imagen_filename)

    print(f"✅ Restaurante creado: {doc['nombre']} — ID: {restaurante_id}")
    return restaurante_id


# ──────────────────────────────────────────────────────────────────────────────
# 2. crear_usuario
# ──────────────────────────────────────────────────────────────────────────────

def crear_usuario(db, datos: dict) -> ObjectId | None:
    """
    Inserta un usuario. Maneja DuplicateKeyError en email (idx_usuarios_email).
    """
    doc = {
        "nombre":   datos["nombre"],
        "apellido": datos.get("apellido", ""),
        "email":    datos["email"],
        "telefono": datos.get("telefono", ""),
        "direccion_default": datos.get("direccion_default", {
            "calle":       "",
            "zona":        "1",
            "ciudad":      "Guatemala City",
            "coordinates": [-90.5069, 14.6407]
        }),
        "historial_pedidos": [],
        "activo":            bool(datos.get("activo", True)),
        "fecha_registro":    datos.get("fecha_registro", datetime.datetime.utcnow())
    }

    try:
        result = db.usuarios.insert_one(doc)
        print(f"✅ Usuario creado: {doc['email']} — ID: {result.inserted_id}")
        return result.inserted_id
    except DuplicateKeyError:
        print(f"❌ DuplicateKeyError: El email '{doc['email']}' ya está registrado.")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 3. crear_menu_item
# ──────────────────────────────────────────────────────────────────────────────

def crear_menu_item(db, datos: dict, imagen_bytes: bytes = None,
                     imagen_filename: str = "imagen.jpg") -> ObjectId:
    """
    Inserta un menu_item referenciando restaurante_id.
    """
    # Verificar que el restaurante existe
    restaurante = db.restaurantes.find_one({"_id": datos["restaurante_id"]})
    if not restaurante:
        raise ValueError(f"Restaurante {datos['restaurante_id']} no encontrado.")

    doc = {
        "restaurante_id":  datos["restaurante_id"],
        "nombre":          datos["nombre"],
        "descripcion":     datos.get("descripcion", ""),
        "precio":          float(datos["precio"]),
        "categorias":      datos.get("categorias", []),
        "ingredientes":    datos.get("ingredientes", []),
        "disponible":      bool(datos.get("disponible", True)),
        "tiempo_prep_min": int(datos.get("tiempo_prep_min", 20)),
        "ventas_total":    int(datos.get("ventas_total", 0)),
        "imagen_id":       None,
        "fecha_creacion":  datos.get("fecha_creacion", datetime.datetime.utcnow())
    }

    result = db.menu_items.insert_one(doc)
    item_id = result.inserted_id

    if imagen_bytes:
        subir_imagen_menu_item(db, item_id, imagen_bytes, imagen_filename)

    print(f"✅ Menu item creado: {doc['nombre']} — ID: {item_id}")
    return item_id


# ──────────────────────────────────────────────────────────────────────────────
# 4. crear_orden (proxy a transacción)
# ──────────────────────────────────────────────────────────────────────────────

def crear_orden(db, usuario_id: ObjectId, restaurante_id: ObjectId,
                items_pedido: list) -> ObjectId:
    """
    Proxy a transactions/orders.py:crear_orden().
    items_pedido: [{'menu_item_id': ObjectId, 'cantidad': int}, ...]
    """
    return _crear_orden_tx(db, usuario_id, restaurante_id, items_pedido)


# ──────────────────────────────────────────────────────────────────────────────
# 5. crear_resena
# ──────────────────────────────────────────────────────────────────────────────

def crear_resena(db, datos: dict) -> ObjectId:
    """Inserta una reseña. JSON Schema valida los campos."""
    doc = {
        "usuario_id":     datos["usuario_id"],
        "restaurante_id": datos["restaurante_id"],
        "calificacion":   int(datos["calificacion"]),
        "comentario":     datos["comentario"],
        "tags":           datos.get("tags", []),
        "util_count":     int(datos.get("util_count", 0)),
        "fecha":          datos.get("fecha", datetime.datetime.utcnow())
    }
    if "orden_id" in datos and datos["orden_id"]:
        doc["orden_id"] = datos["orden_id"]

    result = db.resenas.insert_one(doc)
    print(f"✅ Reseña creada — ID: {result.inserted_id}")
    return result.inserted_id
