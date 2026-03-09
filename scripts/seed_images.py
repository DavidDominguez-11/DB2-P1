"""
scripts/seed_images.py — Parametric Grill Hub
Generador independiente de 100 imágenes ligeras para GridFS.
Usa la librería Pillow (PIL) para crear imágenes locales con texto identificativo.
- 10 para restaurantes
- 90 para menu_items
"""

import sys, os
import io
import random
from PIL import Image, ImageDraw, ImageFont
from bson import ObjectId

# Ajustar path para importar módulos del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import get_db
from gridfs_utils.files import subir_imagen_restaurante, subir_imagen_menu_item

def generar_imagen_bytes(texto: str) -> bytes:
    """Genera una imagen JPG de 400x400 con un color aleatorio y texto."""
    size = (400, 400)
    # Colores oscuros para que el texto blanco resalte
    color = (random.randint(20, 150), random.randint(20, 150), random.randint(20, 150))
    img = Image.new('RGB', size, color=color)
    
    draw = ImageDraw.Draw(img)
    
    # Dibujar texto y un marco visual
    draw.text((30, 180), f"ID: {texto[:22]}...", fill=(255, 255, 255))
    draw.rectangle([15, 15, 385, 385], outline=(255, 255, 255), width=3)
    
    # Guardar en buffer de memoria como JPEG
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()

def seed_images():
    db = get_db()
    print("🚀 Iniciando Seeding Independiente de Imágenes (GridFS)...")

    # 1. Imágenes para Restaurantes (hasta 10)
    restaurantes = list(db.restaurantes.find().limit(10))
    print(f"📸 Procesando {len(restaurantes)} restaurantes...")
    for r in restaurantes:
        img_bytes = generar_imagen_bytes(f"Rest: {r['nombre']}")
        subir_imagen_restaurante(db, r["_id"], img_bytes, filename=f"rest_{r['nombre']}.jpg")

    # 2. Imágenes para Menu Items (hasta 90)
    items = list(db.menu_items.find().limit(90))
    print(f"📸 Procesando {len(items)} items del menú...")
    for i in items:
        img_bytes = generar_imagen_bytes(f"Item: {i['nombre']}")
        subir_imagen_menu_item(db, i["_id"], img_bytes, filename=f"item_{i['nombre']}.jpg")

    print(f"\n✅ Seeding de 100 imágenes completado exitosamente.")
    print("💡 Puedes ejecutar este script en cualquier momento: python scripts/seed_images.py")

if __name__ == "__main__":
    try:
        seed_images()
    except Exception as e:
        print(f"❌ Error durante el seed de imágenes: {e}")
