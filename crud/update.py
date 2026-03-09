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

def actualizar_precios_restaurante(db, restaurante_id: ObjectId,
                                    factor: float) -> int:
    """
    Aplica un factor multiplicador al precio de todos los items del restaurante.
    Ejemplo: factor=1.10 sube precios 10%.
    """
    result = db.menu_items.update_many(
        {"restaurante_id": restaurante_id, "disponible": True},
        {"$mul": {"precio": factor}}
    )
    print(f"✅ Precios actualizados en {result.modified_count} items (×{factor})")
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
    if result.matched_count:
        print(f"✅ Tag '{tag}' agregado a reseña {resena_id} ($addToSet)")
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# 4. update_one — $pull item de orden
# ──────────────────────────────────────────────────────────────────────────────

def quitar_item_orden(db, orden_id: ObjectId, menu_item_id: ObjectId) -> bool:
    """
    Remueve un item del array items de la orden ($pull).
    Solo aplicable en estado 'pendiente'.
    """
    orden = db.ordenes.find_one({"_id": orden_id, "estado": "pendiente"})
    if not orden:
        raise ValueError("Solo se puede editar una orden en estado 'pendiente'.")

    result = db.ordenes.update_one(
        {"_id": orden_id},
        {
            "$pull": {"items": {"menu_item_id": menu_item_id}},
            "$set":  {"fecha_actualizacion": datetime.datetime.utcnow()}
        }
    )
    print(f"✅ Item {menu_item_id} eliminado de orden {orden_id} ($pull)")
    return result.modified_count > 0


# ──────────────────────────────────────────────────────────────────────────────
# 5. update_many — $inc ventas_total (contexto cancelación)
# ──────────────────────────────────────────────────────────────────────────────

def revertir_ventas_total(db, items: list) -> int:
    """
    Decrementa ventas_total para cada item ($inc negativo).
    Usado por cancelar_orden (también implementado en transactions/orders.py).
    """
    count = 0
    for item in items:
        result = db.menu_items.update_many(
            {"_id": item["menu_item_id"]},
            {"$inc": {"ventas_total": -item["cantidad"]}}
        )
        count += result.modified_count
    print(f"✅ ventas_total revertidas en {count} items ($inc negativo)")
    return count


# ──────────────────────────────────────────────────────────────────────────────
# 6. Demostración completa de operadores de array
# ──────────────────────────────────────────────────────────────────────────────

def demo_operadores_array(db) -> dict:
    """
    Demuestra TODOS los operadores de array definidos en Etapa 01, Sección 8.1.
    $push, $pull, $addToSet, $pop, $elemMatch, $size, $inc
    Todos se ejecutan realmente sobre la BD.
    """
    resultados = {}

    # ── $push — Agregar orden al historial del usuario ─────────────────────
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
            "modified_count": res.modified_count
        }
        print(f"✅ $push — historial_pedidos actualizado: {res.modified_count} doc")

        # ── $pop — Eliminar el último elemento del historial ─────────────────
        res_pop = db.usuarios.update_one(
            {"_id": usuario["_id"]},
            {"$pop": {"historial_pedidos": 1}}   # 1 = eliminar último
        )
        resultados["$pop"] = {
            "descripcion": "Eliminar último item del historial_pedidos",
            "documento_id": str(usuario["_id"]),
            "modified_count": res_pop.modified_count
        }
        print(f"✅ $pop — último elemento eliminado: {res_pop.modified_count} doc")

    # ── $addToSet — Agregar tag a reseña sin duplicados ──────────────────────
    resena = db.resenas.find_one()
    if resena:
        res = db.resenas.update_one(
            {"_id": resena["_id"]},
            {"$addToSet": {"tags": "demo_tag"}}
        )
        resultados["$addToSet"] = {
            "descripcion": "Agregar tag único a reseña",
            "documento_id": str(resena["_id"]),
            "modified_count": res.modified_count
        }
        print(f"✅ $addToSet — tag agregado: {res.modified_count} doc")

        # ── $pull — Remover el tag recién agregado ────────────────────────────
        res_pull = db.resenas.update_one(
            {"_id": resena["_id"]},
            {"$pull": {"tags": "demo_tag"}}
        )
        resultados["$pull"] = {
            "descripcion": "Remover tag de reseña",
            "documento_id": str(resena["_id"]),
            "modified_count": res_pull.modified_count
        }
        print(f"✅ $pull — tag removido: {res_pull.modified_count} doc")

    # ── $elemMatch — Filtrar órdenes con item específico ────────────────────
    menu_item = db.menu_items.find_one()
    if menu_item:
        ordenes_con_item = list(db.ordenes.find(
            {"items": {"$elemMatch": {"menu_item_id": menu_item["_id"]}}},
            {"_id": 1, "estado": 1}
        ).limit(5))
        resultados["$elemMatch"] = {
            "descripcion": "Órdenes que contienen un item específico",
            "menu_item_id": str(menu_item["_id"]),
            "count_encontradas": len(ordenes_con_item)
        }
        print(f"✅ $elemMatch — órdenes con item: {len(ordenes_con_item)}")

    # ── $size — Órdenes con exactamente 3 items ──────────────────────────────
    ordenes_3_items = db.ordenes.count_documents(
        {"items": {"$size": 3}}
    )
    resultados["$size"] = {
        "descripcion": "Órdenes con exactamente 3 artículos",
        "count": ordenes_3_items
    }
    print(f"✅ $size — órdenes con 3 items: {ordenes_3_items}")

    # ── $inc — Incrementar ventas_total ──────────────────────────────────────
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
        print(f"✅ $inc — ventas_total incrementado: {res_inc.modified_count} doc")

    print("\n✅ Demo de operadores de array completada.")
    return resultados
