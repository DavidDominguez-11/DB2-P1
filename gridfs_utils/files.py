"""
gridfs_utils/files.py — Parametric Grill Hub
Manejo de imágenes con GridFS.
- Subida imagen restaurante
- Subida imagen menu_item
- Recuperación por imagen_id
NO almacenar binarios dentro de documentos.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bson import ObjectId
from gridfs.errors import GridFSError
from config import get_db, get_gridfs


def subir_imagen_restaurante(db, restaurante_id: ObjectId, imagen_bytes: bytes,
                              filename: str = "imagen.jpg",
                              content_type: str = "image/jpeg") -> ObjectId:
    """
    Sube una imagen de restaurante a GridFS y actualiza imagen_id en el documento.
    Retorna el ObjectId del archivo en GridFS.
    """
    fs = get_gridfs()
    imagen_id = fs.put(
        imagen_bytes,
        filename=filename,
        content_type=content_type,
        restaurante_id=restaurante_id,
        tipo="restaurante"
    )

    db.restaurantes.update_one(
        {"_id": restaurante_id},
        {"$set": {"imagen_id": imagen_id}}
    )

    print(f"✅ Imagen restaurante subida a GridFS: {imagen_id}")
    return imagen_id


def subir_imagen_menu_item(db, menu_item_id: ObjectId, imagen_bytes: bytes,
                            filename: str = "imagen.jpg",
                            content_type: str = "image/jpeg") -> ObjectId:
    """
    Sube una imagen de menu_item a GridFS y actualiza imagen_id en el documento.
    """
    fs = get_gridfs()
    imagen_id = fs.put(
        imagen_bytes,
        filename=filename,
        content_type=content_type,
        menu_item_id=menu_item_id,
        tipo="menu_item"
    )

    db.menu_items.update_one(
        {"_id": menu_item_id},
        {"$set": {"imagen_id": imagen_id}}
    )

    print(f"✅ Imagen menu_item subida a GridFS: {imagen_id}")
    return imagen_id


def recuperar_imagen(imagen_id: ObjectId) -> bytes | None:
    """
    Recupera los bytes de una imagen almacenada en GridFS por su ObjectId.
    Retorna None si no existe.
    """
    fs = get_gridfs()
    try:
        grid_out = fs.get(imagen_id)
        return grid_out.read()
    except Exception as e:
        print(f"⚠️  No se pudo recuperar imagen {imagen_id}: {e}")
        return None


def recuperar_metadata(imagen_id: ObjectId) -> dict | None:
    """Retorna metadata del archivo GridFS (filename, content_type, etc.)."""
    fs = get_gridfs()
    try:
        grid_out = fs.get(imagen_id)
        return {
            "filename":     grid_out.filename,
            "content_type": grid_out.content_type,
            "length":       grid_out.length,
            "upload_date":  grid_out.upload_date,
        }
    except Exception as e:
        print(f"⚠️  Metadata no disponible para {imagen_id}: {e}")
        return None


def eliminar_imagen(imagen_id: ObjectId) -> bool:
    """Elimina un archivo de GridFS por su ObjectId."""
    fs = get_gridfs()
    try:
        fs.delete(imagen_id)
        print(f"🗑️  Imagen {imagen_id} eliminada de GridFS.")
        return True
    except Exception as e:
        print(f"⚠️  No se pudo eliminar imagen {imagen_id}: {e}")
        return False
