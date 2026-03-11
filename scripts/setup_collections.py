"""
scripts/setup_collections.py — Parametric Grill Hub
ORDEN OBLIGATORIO:
  Paso 1 — Crear colecciones con JSON Schema (restaurantes, ordenes, resenas)
  Paso 2 — Crear los 9 índices exactos
  Paso 3 — Activar notablescan=1 DESPUÉS de todos los índices

NO modificar nombres de campos, tipos ni validationAction/Level.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pymongo import ASCENDING, DESCENDING, TEXT, GEOSPHERE
from pymongo.errors import CollectionInvalid, OperationFailure
from config import get_db, get_client


# ──────────────────────────────────────────────────────────────────────────────
# JSON SCHEMA VALIDATORS — EXACTAMENTE como en Etapa 01
# ──────────────────────────────────────────────────────────────────────────────

VALIDATOR_RESTAURANTES = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["nombre", "categorias", "ubicacion", "activo", "fecha_registro"],
        "properties": {
            "nombre": {
                "bsonType": "string",
                "description": "Nombre del restaurante — requerido"
            },
            "descripcion": {"bsonType": "string"},
            "telefono":    {"bsonType": "string"},
            "email": {
                "bsonType": "string",
                "pattern": "^.+@.+\\..+$"
            },
            "categorias": {
                "bsonType": "array",
                "minItems": 1,
                "items": {"bsonType": "string"}
            },
            "ubicacion": {
                "bsonType": "object",
                "required": ["type", "coordinates"],
                "properties": {
                    "type": {"bsonType": "string", "enum": ["Point"]},
                    "coordinates": {"bsonType": "array", "minItems": 2, "maxItems": 2}
                }
            },
            "calificacion_promedio": {
                "bsonType": "double",
                "minimum": 0,
                "maximum": 5
            },
            "activo":         {"bsonType": "bool"},
            "fecha_registro": {"bsonType": "date"}
        }
    }
}

VALIDATOR_ORDENES = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "usuario_id", "restaurante_id", "items",
            "estado", "total", "fecha_creacion"
        ],
        "properties": {
            "usuario_id":     {"bsonType": "objectId"},
            "restaurante_id": {"bsonType": "objectId"},
            "items": {
                "bsonType": "array",
                "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": [
                        "menu_item_id", "nombre", "cantidad",
                        "precio_unitario", "subtotal"
                    ],
                    "properties": {
                        "menu_item_id":    {"bsonType": "objectId"},
                        "nombre":          {"bsonType": "string"},
                        "cantidad":        {"bsonType": "int",    "minimum": 1},
                        "precio_unitario": {"bsonType": "double", "minimum": 0},
                        "subtotal":        {"bsonType": "double", "minimum": 0}
                    }
                }
            },
            "estado": {
                "bsonType": "string",
                "enum": [
                    "pendiente", "confirmado", "en_preparacion",
                    "en_camino", "entregado", "cancelado"
                ]
            },
            "total":          {"bsonType": "double", "minimum": 0},
            "fecha_creacion": {"bsonType": "date"}
        }
    }
}

VALIDATOR_RESENAS = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "usuario_id", "restaurante_id",
            "calificacion", "comentario", "fecha"
        ],
        "properties": {
            "usuario_id":     {"bsonType": "objectId"},
            "restaurante_id": {"bsonType": "objectId"},
            "orden_id":       {"bsonType": "objectId"},
            "calificacion":   {"bsonType": "int", "minimum": 1, "maximum": 5},
            "comentario":     {"bsonType": "string", "minLength": 5},
            "tags":           {"bsonType": "array", "items": {"bsonType": "string"}},
            "util_count":     {"bsonType": "int", "minimum": 0},
            "fecha":          {"bsonType": "date"}
        }
    }
}


# ──────────────────────────────────────────────────────────────────────────────
# PASO 1 — Crear colecciones con JSON Schema
# ──────────────────────────────────────────────────────────────────────────────

def crear_colecciones(db):
    """
    Crea las 5 colecciones.
    restaurantes, ordenes, resenas → con JSON Schema validator.
    usuarios, menu_items → sin validator de schema (definidos implícitamente).
    """
    existing = db.list_collection_names()

    # restaurantes
    if "restaurantes" not in existing:
        db.create_collection(
            "restaurantes",
            validator=VALIDATOR_RESTAURANTES,
            validationAction="error",
            validationLevel="strict"
        )
        print("✅ Colección 'restaurantes' creada con JSON Schema.")
    else:
        # Actualizar el validator si ya existe
        db.command("collMod", "restaurantes",
                   validator=VALIDATOR_RESTAURANTES,
                   validationAction="error",
                   validationLevel="strict")
        print("⚠️  Colección 'restaurantes' ya existía — validator actualizado.")

    # ordenes
    if "ordenes" not in existing:
        db.create_collection(
            "ordenes",
            validator=VALIDATOR_ORDENES,
            validationAction="error",
            validationLevel="strict"
        )
        print("✅ Colección 'ordenes' creada con JSON Schema.")
    else:
        db.command("collMod", "ordenes",
                   validator=VALIDATOR_ORDENES,
                   validationAction="error",
                   validationLevel="strict")
        print("⚠️  Colección 'ordenes' ya existía — validator actualizado.")

    # resenas
    if "resenas" not in existing:
        db.create_collection(
            "resenas",
            validator=VALIDATOR_RESENAS,
            validationAction="error"
        )
        print("✅ Colección 'resenas' creada con JSON Schema.")
    else:
        db.command("collMod", "resenas",
                   validator=VALIDATOR_RESENAS,
                   validationAction="error")
        print("⚠️  Colección 'resenas' ya existía — validator actualizado.")

    # usuarios (sin validator explícito)
    if "usuarios" not in existing:
        db.create_collection("usuarios")
        print("✅ Colección 'usuarios' creada.")
    else:
        print("⚠️  Colección 'usuarios' ya existía.")

    # menu_items (sin validator explícito)
    if "menu_items" not in existing:
        db.create_collection("menu_items")
        print("✅ Colección 'menu_items' creada.")
    else:
        print("⚠️  Colección 'menu_items' ya existía.")


# ──────────────────────────────────────────────────────────────────────────────
# PASO 2 — Crear los 9 índices con nombres EXACTOS
# ──────────────────────────────────────────────────────────────────────────────

def crear_indices(db):
    """
    Crea exactamente los 9 índices definidos en la Etapa 01.
    Nombres de índice: EXACTOS según la especificación.
    """

    # 1. usuarios.email — unique simple
    db.usuarios.create_index(
        [("email", ASCENDING)],
        unique=True,
        name="idx_usuarios_email"
    )
    print("✅ Índice 1: idx_usuarios_email (unique)")

    # 2. ordenes {usuario_id, fecha_creacion} — compuesto
    db.ordenes.create_index(
        [("usuario_id", ASCENDING), ("fecha_creacion", DESCENDING)],
        name="idx_ordenes_usuario_fecha"
    )
    print("✅ Índice 2: idx_ordenes_usuario_fecha (compuesto)")

    # 3. ordenes {restaurante_id, estado} — compuesto
    db.ordenes.create_index(
        [("restaurante_id", ASCENDING), ("estado", ASCENDING)],
        name="idx_ordenes_restaurante_estado"
    )
    print("✅ Índice 3: idx_ordenes_restaurante_estado (compuesto)")

    # 4. restaurantes.categorias — multikey
    db.restaurantes.create_index(
        [("categorias", ASCENDING)],
        name="idx_restaurantes_categorias"
    )
    print("✅ Índice 4: idx_restaurantes_categorias (multikey)")

    # 5. menu_items.categorias — multikey
    db.menu_items.create_index(
        [("categorias", ASCENDING)],
        name="idx_menu_categorias"
    )
    print("✅ Índice 5: idx_menu_categorias (multikey)")

    # 6. resenas.tags — multikey
    db.resenas.create_index(
        [("tags", ASCENDING)],
        name="idx_resenas_tags"
    )
    print("✅ Índice 6: idx_resenas_tags (multikey)")

    # 7. restaurantes.ubicacion — 2dsphere
    db.restaurantes.create_index(
        [("ubicacion", GEOSPHERE)],
        name="idx_restaurantes_geo"
    )
    print("✅ Índice 7: idx_restaurantes_geo (2dsphere)")

    # 8. menu_items text index — nombre weight:10, descripcion weight:5
    db.menu_items.create_index(
        [("nombre", TEXT), ("descripcion", TEXT)],
        weights={"nombre": 10, "descripcion": 5},
        name="idx_menu_texto"
    )
    print("✅ Índice 8: idx_menu_texto (text, weights nombre:10 descripcion:5)")

    # 9. resenas text index — comentario
    db.resenas.create_index(
        [("comentario", TEXT)],
        name="idx_resenas_texto"
    )
    print("✅ Índice 9: idx_resenas_texto (text)")

    print("\n📋 Índices creados correctamente:")
    for col in ["usuarios", "ordenes", "restaurantes", "menu_items", "resenas"]:
        indices = list(db[col].list_indexes())
        for idx in indices:
            print(f"   [{col}] {idx['name']}")


# ──────────────────────────────────────────────────────────────────────────────
# PASO 3 — Activar notablescan=1 DESPUÉS de crear todos los índices
# ──────────────────────────────────────────────────────────────────────────────

def activar_notablescan(db):
    """
    Activa el rechazo de consultas sin índice.
    DEBE ejecutarse DESPUÉS de crear todos los índices.
    ⚠️  No funciona en MongoDB Atlas (servicio administrado); sí en Atlas local/Docker.
    """
    try:
        result = db.command("setParameter", 1, notablescan=1)
        print(f"\n🔒 notablescan=1 activado. Resultado: {result}")

        # Verificar
        verify = db.command("getParameter", 1, notablescan=1)
        print(f"   Verificación: notablescan = {verify.get('notablescan')}")
    except OperationFailure as e:
        print(f"\n⚠️  No se pudo activar notablescan (puede ser Atlas administrado): {e}")
        print("   En Atlas M0/Shared, usar query planner hints o index hints como alternativa.")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN — Ejecutar en orden obligatorio
# ──────────────────────────────────────────────────────────────────────────────

def setup(db=None):
    if db is None:
        db = get_db()

    print("=" * 60)
    print("  Parametric Grill Hub — Setup de Colecciones e Índices")
    print("=" * 60)

    print("\n── PASO 1: Crear colecciones con JSON Schema ──────────────")
    crear_colecciones(db)

    print("\n── PASO 2: Crear índices ───────────────────────────────────")
    crear_indices(db)

    print("\n── PASO 3: Activar notablescan=1 ──────────────────────────")
    activar_notablescan(db)

    print("\n✅ Setup completo.\n")
    return db


if __name__ == "__main__":
    setup()
