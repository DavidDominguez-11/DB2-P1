"""
crud/update.py — Parametric Grill Hub
UPDATE operations (10 pts) + Manejo de Arrays (10 pts):

1. update_one — cambiar estado de orden
2. update_many — actualizar precios con $mul
3. update_one  — $addToSet tags en reseña
4. update_one  — $pull item de orden
5. update_many — $inc ventas_total (transacción cancelación)
6. Demostración completa de operadores de array:
   $push, $pull, $addToSet, $pop, $elemMatch, $size, $inc
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import datetime
from bson import ObjectId
from pymongo import ASCENDING
from config import get_db

ESTADOS_VALIDOS = ["pendiente", "confirmado", "en_preparacion",
                   "en_camino", "entregado", "cancelado"]


# ──────────────────────────────────────────────────────────────────────────────
# 1. update_one — cambiar estado de orden
# ──────────────────────────────────────────────────────────────────────────────

def cambiar_estado_orden(db, orden_id: ObjectId, nuevo_estado: str) -> bool:
    """
    Cambia el estado de una orden. JSON Schema valida el enum.
    """
    if nuevo_estado not in ESTADOS_VALIDOS:
        raise ValueError(f"Estado '{nuevo_estado}' no válido. Debe ser uno de: {ESTADOS_VALIDOS}")

    result = db.ordenes.update_one(
        {"_id": orden_id},
        {
            "$set": {
                "estado":              nuevo_estado,
                "fecha_actualizacion": datetime.datetime.utcnow()
            }
        }
    )
    if result.matched_count:
        print(f"✅ Orden {orden_id} → estado: {nuevo_estado}")
        return True
    print(f"⚠️  Orden {orden_id} no encontrada.")
    return False


# ──────────────────────────────────────────────────────────────────────────────
# 2. update_many — actualizar precios con $mul
# ──────────────────────────────────────────────────────────────────────────────

def actualizar_precios_restaurante(db, restaurante_id: ObjectId, factor: float) -> int:
    """
    Multiplica el precio de todos los items de un restaurante ($mul).
    """
    result = db.menu_items.update_many(
        {"restaurante_id": restaurante_id},
        {
            "$mul": {"precio": factor},
            "$set": {"fecha_actualizacion": datetime.datetime.utcnow()}
        }
    )
    print(f"✅ Items del restaurante {restaurante_id} actualizados con factor {factor} ($mul)")
    return result.modified_count


# ──────────────────────────────────────────────────────────────────────────────
# 3. update_one — $addToSet tags en reseña (sin duplicados)
# ──────────────────────────────────────────────────────────────────────────────

def agregar_tag_resena(db, resena_id: ObjectId, tag: str) -> bool:
    """
    Agrega un tag a una reseña sin permitir duplicados ($addToSet).
    """
    result = db.resenas.update_one(
        {"_id": resena_id},
        {"$addToSet": {"tags": tag}}
    )
    if result.modified_count:
        print(f"✅ Tag '{tag}' agregado a reseña {resena_id} ($addToSet)")
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# 4. update_one — $pull item de orden
# ──────────────────────────────────────────────────────────────────────────────

def quitar_item_orden(db, orden_id: ObjectId, menu_item_id: ObjectId) -> bool:
    """
    Remueve un item del array items de la orden ($pull).
    """
    result = db.ordenes.update_one(
        {"_id": orden_id},
        {
            "$pull": {"items": {"menu_item_id": menu_item_id}},
            "$set":  {"fecha_actualizacion": datetime.datetime.utcnow()}
        }
    )
    if result.modified_count:
        print(f"✅ Item {menu_item_id} eliminado de orden {orden_id} ($pull)")
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# 5. update_many — $inc ventas_total (contexto cancelación)
# ──────────────────────────────────────────────────────────────────────────────

def revertir_ventas_total(db, items_list: list) -> int:
    """
    Decrementa ventas_total para cada item ($inc negativo).
    """
    count = 0
    for item in items_list:
        res = db.menu_items.update_one(
            {"_id": item["menu_item_id"]},
            {"$inc": {"ventas_total": -item["cantidad"]}}
        )
        count += res.modified_count
    print(f"✅ ventas_total revertidas en {count} items ($inc negativo)")
    return count


# ──────────────────────────────────────────────────────────────────────────────
# 6. Demostración completa de operadores de array (10 pts)
# ──────────────────────────────────────────────────────────────────────────────

def demo_push_pop(db):
    """Demostración de $push y $pop."""
    resultados = {}
    usuario = db.usuarios.find_one({"activo": True})
    if usuario:
        orden_ficticia = ObjectId()
        res = db.usuarios.update_one(
            {"_id": usuario["_id"]},
            {"$push": {"historial_pedidos": orden_ficticia}}
        )
        resultados["$push"] = {
            "descripcion": "Agregar orden al historial del usuario",
            "documento_id": str(usuario["_id"]),
            "modified_count": res.modified_count,
            "valor_agregado": str(orden_ficticia)
        }

        res_pop = db.usuarios.update_one(
            {"_id": usuario["_id"]},
            {"$pop": {"historial_pedidos": 1}}   # 1 = eliminar último
        )
        resultados["$pop"] = {
            "descripcion": "Eliminar último item del historial_pedidos",
            "documento_id": str(usuario["_id"]),
            "modified_count": res_pop.modified_count
        }
    return resultados

def demo_addtoset_pull(db):
    """Demostración de $addToSet y $pull."""
    resultados = {}
    resena = db.resenas.find_one()
    if resena:
        tag_demo = "demo_tag"
        res = db.resenas.update_one(
            {"_id": resena["_id"]},
            {"$addToSet": {"tags": tag_demo}}
        )
        resultados["$addToSet"] = {
            "descripcion": "Agregar tag único a reseña",
            "documento_id": str(resena["_id"]),
            "modified_count": res.modified_count,
            "tag": tag_demo
        }

        res_pull = db.resenas.update_one(
            {"_id": resena["_id"]},
            {"$pull": {"tags": tag_demo}}
        )
        resultados["$pull"] = {
            "descripcion": "Remover tag de reseña",
            "documento_id": str(resena["_id"]),
            "modified_count": res_pull.modified_count,
            "tag": tag_demo
        }
    return resultados

def demo_elemmatch(db):
    """Demostración de $elemMatch."""
    resultados = {}
    menu_item = db.menu_items.find_one()
    if menu_item:
        ordenes_con_item = list(db.ordenes.find(
            {"items": {"$elemMatch": {"menu_item_id": menu_item["_id"]}}},
            {"_id": 1, "estado": 1}
        ).limit(5))
        resultados["$elemMatch"] = {
            "descripcion": "Órdenes que contienen un item específico",
            "menu_item_id": str(menu_item["_id"]),
            "count_encontradas": len(ordenes_con_item),
            "ejemplos_ids": [str(o["_id"]) for o in ordenes_con_item]
        }
    return resultados

def demo_size(db):
    """Demostración de $size."""
    resultados = {}
    counts = {}
    for n in [1, 2, 3]:
        c = db.ordenes.count_documents({"items": {"$size": n}})
        counts[f"tamaño_{n}"] = c

    resultados["$size"] = {
        "descripcion": "Contar órdenes por número exacto de artículos",
        "resultados": counts
    }
    return resultados

def demo_inc(db):
    """Demostración de $inc."""
    resultados = {}
    menu_item = db.menu_items.find_one()
    if menu_item:
        res_inc = db.menu_items.update_one(
            {"_id": menu_item["_id"]},
            {"$inc": {"ventas_total": 1}}
        )
        resultados["$inc"] = {
            "descripcion": "Incrementar ventas_total de menu_item",
            "menu_item_id": str(menu_item["_id"]),
            "modified_count": res_inc.modified_count
        }
    return resultados

def demo_operadores_array(db):
    """
    Ejecuta una demostración real sobre la BD de:
    $push, $pull, $addToSet, $pop, $elemMatch, $size, $inc
    """
    resultados = {}
    resultados.update(demo_push_pop(db))
    resultados.update(demo_addtoset_pull(db))
    resultados.update(demo_elemmatch(db))
    resultados.update(demo_size(db))
    resultados.update(demo_inc(db))

    print("\n✅ Demo de operadores de array completada.")
    return resultados
