"""
transactions/orders.py — Parametric Grill Hub
Transacciones Multi-Documento:
  1. crear_orden()   — 7 pasos atómicos (Sección 4.1)
  2. cancelar_orden() — revertir ventas_total (Sección 4.2)

Exactamente como se define en Etapa 01.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import datetime
from bson import ObjectId
from pymongo.errors import PyMongoError
from config import get_db, get_client


# ──────────────────────────────────────────────────────────────────────────────
# 4.1 Transacción: Creación de una Nueva Orden
# ──────────────────────────────────────────────────────────────────────────────

def crear_orden(db, usuario_id: ObjectId, restaurante_id: ObjectId,
                items_pedido: list) -> ObjectId:
    """
    Transacción multi-documento para crear una orden.
    Pasos (EXACTOS según Etapa 01):
      1. findOne — verificar usuario activo
      2. findOne — verificar restaurante activo
      3. find    — verificar disponibilidad de cada item + snapshot precio
      4. insertOne orden con estado='pendiente'
      5. updateOne $push historial_pedidos
      6. updateOne $inc ventas_total (por cada item)
      7. commitTransaction (automático al salir del with)

    items_pedido: [{'menu_item_id': ObjectId, 'cantidad': int}, ...]
    """
    client = get_client()

    with client.start_session() as session:
        with session.start_transaction():

            # Paso 1 — validar usuario activo
            usuario = db.usuarios.find_one(
                {"_id": usuario_id, "activo": True},
                session=session
            )
            if not usuario:
                raise ValueError("Usuario no encontrado o inactivo")

            # Paso 2 — validar restaurante activo
            restaurante = db.restaurantes.find_one(
                {"_id": restaurante_id, "activo": True},
                session=session
            )
            if not restaurante:
                raise ValueError("Restaurante no encontrado o inactivo")

            # Paso 3 — validar disponibilidad items + construir snapshot precio
            items_orden = []
            total = 0.0
            for item in items_pedido:
                mi = db.menu_items.find_one(
                    {"_id": item["menu_item_id"], "disponible": True},
                    session=session
                )
                if not mi:
                    raise ValueError(f"Item {item['menu_item_id']} no disponible")

                subtotal = round(float(mi["precio"]) * int(item["cantidad"]), 2)
                items_orden.append({
                    "menu_item_id":    mi["_id"],
                    "nombre":          mi["nombre"],
                    "cantidad":        int(item["cantidad"]),   # int para JSON Schema
                    "precio_unitario": float(mi["precio"]),     # double para JSON Schema
                    "subtotal":        float(subtotal)
                })
                total += subtotal

            # Paso 4 — crear la orden con snapshot de precios
            nueva_orden = {
                "usuario_id":          usuario_id,
                "restaurante_id":      restaurante_id,
                "items":               items_orden,
                "estado":              "pendiente",
                "total":               round(total, 2),
                "notas":               "",
                "direccion_entrega":   usuario.get("direccion_default", {}),
                "fecha_creacion":      datetime.datetime.utcnow(),
                "fecha_actualizacion": datetime.datetime.utcnow()
            }
            result = db.ordenes.insert_one(nueva_orden, session=session)
            orden_id = result.inserted_id

            # Paso 5 — actualizar historial del usuario ($push)
            db.usuarios.update_one(
                {"_id": usuario_id},
                {"$push": {"historial_pedidos": orden_id}},
                session=session
            )

            # Paso 6 — incrementar ventas_total de cada item ($inc)
            for item in items_orden:
                db.menu_items.update_one(
                    {"_id": item["menu_item_id"]},
                    {"$inc": {"ventas_total": item["cantidad"]}},
                    session=session
                )

            # Paso 7 — commitTransaction automático al salir del `with`
            print(f"✅ Orden creada exitosamente: {orden_id}")
            return orden_id


# ──────────────────────────────────────────────────────────────────────────────
# 4.2 Transacción: Cancelación de Orden
# ──────────────────────────────────────────────────────────────────────────────

def cancelar_orden(db, orden_id: ObjectId) -> bool:
    """
    Transacción multi-documento para cancelar una orden.
    Solo se puede cancelar en estado 'pendiente' o 'confirmado'.
    Pasos (Etapa 01, Sección 4.2):
      1. Verificar estado in ['pendiente', 'confirmado']
      2. updateOne $set estado='cancelado'
      3. updateMany $inc ventas_total con valor negativo por cada item
    """
    client = get_client()

    with client.start_session() as session:
        with session.start_transaction():

            # Paso 1 — verificar estado permitido
            orden = db.ordenes.find_one(
                {"_id": orden_id},
                session=session
            )
            if not orden:
                raise ValueError(f"Orden {orden_id} no encontrada")

            if orden["estado"] not in ["pendiente", "confirmado"]:
                raise ValueError(
                    f"No se puede cancelar una orden en estado '{orden['estado']}'. "
                    f"Solo se permite cancelar 'pendiente' o 'confirmado'."
                )

            # Paso 2 — cambiar estado a 'cancelado'
            db.ordenes.update_one(
                {"_id": orden_id},
                {
                    "$set": {
                        "estado":              "cancelado",
                        "fecha_actualizacion": datetime.datetime.utcnow()
                    }
                },
                session=session
            )

            # Paso 3 — revertir ventas_total con $inc negativo
            for item in orden.get("items", []):
                db.menu_items.update_one(
                    {"_id": item["menu_item_id"]},
                    {"$inc": {"ventas_total": -item["cantidad"]}},
                    session=session
                )

            print(f"✅ Orden {orden_id} cancelada. ventas_total revertidas.")
            return True
