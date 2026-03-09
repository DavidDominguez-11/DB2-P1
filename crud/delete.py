"""
crud/delete.py — Parametric Grill Hub
DELETE operations (10 pts):
  1. delete_one  — eliminar menu_item por _id
  2. delete_many — eliminar reseñas por usuario_id
  3. soft delete — restaurante activo=False (conserva historial)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import datetime
from bson import ObjectId
from config import get_db


# ──────────────────────────────────────────────────────────────────────────────
# 1. delete_one — menu_item
# ──────────────────────────────────────────────────────────────────────────────

def eliminar_menu_item(db, menu_item_id: ObjectId) -> bool:
    """
    Elimina un artículo del menú por _id (delete_one).
    Verifica que exista antes de eliminar.
    """
    item = db.menu_items.find_one({"_id": menu_item_id})
    if not item:
        print(f"⚠️  Menu item {menu_item_id} no encontrado.")
        return False

    result = db.menu_items.delete_one({"_id": menu_item_id})
    if result.deleted_count:
        print(f"🗑️  Menu item '{item['nombre']}' ({menu_item_id}) eliminado.")
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# 2. delete_many — reseñas por usuario_id
# ──────────────────────────────────────────────────────────────────────────────

def eliminar_resenas_usuario(db, usuario_id: ObjectId) -> int:
    """
    Elimina todas las reseñas de un usuario (delete_many).
    Retorna el número de documentos eliminados.
    """
    result = db.resenas.delete_many({"usuario_id": usuario_id})
    print(f"🗑️  {result.deleted_count} reseña(s) del usuario {usuario_id} eliminadas.")
    return result.deleted_count


def eliminar_resena(db, resena_id: ObjectId) -> bool:
    """
    Elimina una reseña específica por su ID (delete_one).
    """
    result = db.resenas.delete_one({"_id": resena_id})
    if result.deleted_count:
        print(f"🗑️  Reseña {resena_id} eliminada.")
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# 3. Soft delete — restaurante (activo=False)
# ──────────────────────────────────────────────────────────────────────────────

def soft_delete_restaurante(db, restaurante_id: ObjectId) -> bool:
    """
    Soft delete: marca el restaurante como inactivo (activo=False).
    Conserva el historial completo de órdenes y reseñas.
    """
    result = db.restaurantes.update_one(
        {"_id": restaurante_id},
        {
            "$set": {
                "activo": False,
            }
        }
    )
    if result.matched_count:
        print(f"🔒 Restaurante {restaurante_id} desactivado (soft delete).")
        return True
    print(f"⚠️  Restaurante {restaurante_id} no encontrado.")
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Utilidad: Restaurar restaurante (revertir soft delete)
# ──────────────────────────────────────────────────────────────────────────────

def restaurar_restaurante(db, restaurante_id: ObjectId) -> bool:
    """Reactiva un restaurante previamente desactivado."""
    result = db.restaurantes.update_one(
        {"_id": restaurante_id},
        {"$set": {"activo": True}}
    )
    if result.matched_count:
        print(f"✅ Restaurante {restaurante_id} reactivado.")
        return True
    return False
