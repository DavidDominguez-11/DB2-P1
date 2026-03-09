"""
scripts/seed.py — Parametric Grill Hub
Genera datos iniciales:
  - 10 restaurantes de ejemplo
  - 20 usuarios de ejemplo
  - 50 menu_items de ejemplo
  - 50,000 órdenes históricas usando BulkWrite + InsertOne (ordered=False)
  - 200 reseñas de ejemplo

Script de seeding exactamente como está definido en Etapa 01, Sección 7.3.
"""

import sys, os, random, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pymongo import InsertOne
from pymongo.errors import BulkWriteError
from bson import ObjectId
from config import get_db, get_gridfs
import io

# Faker para datos realistas
try:
    from faker import Faker
    fake = Faker("es_MX")
except ImportError:
    fake = None


# ──────────────────────────────────────────────────────────────────────────────
# Datos base de Guatemala City para ubicaciones
# ──────────────────────────────────────────────────────────────────────────────

RESTAURANTES_BASE = [
    {"nombre": "El Fogón Chapín",        "categorias": ["guatemalteca", "asados"],   "lng": -90.5069, "lat": 14.6407},
    {"nombre": "Taquería La Morenita",   "categorias": ["mexicana", "tacos"],        "lng": -90.5120, "lat": 14.6380},
    {"nombre": "Sushi Zen Guatemala",    "categorias": ["japonesa", "sushi"],        "lng": -90.5200, "lat": 14.6450},
    {"nombre": "La Pasta Nostra",        "categorias": ["italiana", "pasta"],        "lng": -90.5050, "lat": 14.6500},
    {"nombre": "Burger Republic",        "categorias": ["americana", "hamburguesas"],"lng": -90.5300, "lat": 14.6350},
    {"nombre": "Pollo Campero Original", "categorias": ["pollo", "guatemalteca"],    "lng": -90.5150, "lat": 14.6420},
    {"nombre": "El Rincón del Chef",     "categorias": ["fusión", "gourmet"],        "lng": -90.5080, "lat": 14.6460},
    {"nombre": "Mariscos del Pacífico",  "categorias": ["mariscos", "pescados"],     "lng": -90.5250, "lat": 14.6390},
    {"nombre": "Veggie Paradise",        "categorias": ["vegetariana", "vegana"],    "lng": -90.5100, "lat": 14.6430},
    {"nombre": "La Churrería Madrileña", "categorias": ["española", "desayunos"],    "lng": -90.5180, "lat": 14.6410},
]

MENU_POR_RESTAURANTE = {
    0: [  # El Fogón Chapín
        {"nombre": "Carne Asada con Chirmol",    "precio": 85.0,  "categorias": ["carnes", "principal"]},
        {"nombre": "Pepián de Res",              "precio": 70.0,  "categorias": ["guatemalteco", "principal"]},
        {"nombre": "Kak'ik de Chompipe",         "precio": 90.0,  "categorias": ["guatemalteco", "sopa"]},
        {"nombre": "Frijoles Volteados",         "precio": 25.0,  "categorias": ["guatemalteco", "acompañamiento"]},
        {"nombre": "Atol de Elote",              "precio": 20.0,  "categorias": ["bebida", "tradicional"]},
    ],
    1: [  # Taquería La Morenita
        {"nombre": "Taco de Pastor",             "precio": 18.0,  "categorias": ["taco", "cerdo"]},
        {"nombre": "Taco de Birria",             "precio": 22.0,  "categorias": ["taco", "res"]},
        {"nombre": "Burrito XXL",                "precio": 55.0,  "categorias": ["burrito", "principal"]},
        {"nombre": "Quesadilla de Pollo",        "precio": 45.0,  "categorias": ["quesadilla", "pollo"]},
        {"nombre": "Agua de Jamaica",            "precio": 15.0,  "categorias": ["bebida"]},
    ],
    2: [  # Sushi Zen
        {"nombre": "Sushi Roll California",      "precio": 65.0,  "categorias": ["sushi", "mariscos"]},
        {"nombre": "Ramen Tonkotsu",             "precio": 85.0,  "categorias": ["ramen", "sopas"]},
        {"nombre": "Sashimi Premium 12 pzs",     "precio": 120.0, "categorias": ["sashimi", "premium"]},
        {"nombre": "Gyoza (8 piezas)",           "precio": 45.0,  "categorias": ["aperitivo"]},
        {"nombre": "Té Verde Matcha",            "precio": 25.0,  "categorias": ["bebida"]},
    ],
    3: [  # La Pasta Nostra
        {"nombre": "Spaghetti Carbonara",        "precio": 75.0,  "categorias": ["pasta", "principal"]},
        {"nombre": "Lasagna Bolognesa",          "precio": 80.0,  "categorias": ["pasta", "principal"]},
        {"nombre": "Pizza Margherita",           "precio": 95.0,  "categorias": ["pizza", "principal"]},
        {"nombre": "Tiramisú",                   "precio": 40.0,  "categorias": ["postre"]},
        {"nombre": "Limonada Italiana",          "precio": 30.0,  "categorias": ["bebida"]},
    ],
    4: [  # Burger Republic
        {"nombre": "Classic Smash Burger",       "precio": 70.0,  "categorias": ["hamburguesa", "res"]},
        {"nombre": "BBQ Bacon Double",           "precio": 90.0,  "categorias": ["hamburguesa", "premium"]},
        {"nombre": "Cheese Fries",               "precio": 35.0,  "categorias": ["acompañamiento"]},
        {"nombre": "Milkshake Oreo",             "precio": 45.0,  "categorias": ["bebida", "postre"]},
        {"nombre": "Veggie Burger",              "precio": 65.0,  "categorias": ["hamburguesa", "vegetariana"]},
    ],
    5: [  # Pollo Campero
        {"nombre": "Pollo Crujiente 3 piezas",   "precio": 60.0,  "categorias": ["pollo", "principal"]},
        {"nombre": "Combo Familiar 12 pzs",      "precio": 185.0, "categorias": ["pollo", "familiar"]},
        {"nombre": "Ensalada César",             "precio": 45.0,  "categorias": ["ensalada"]},
        {"nombre": "Papas Fritas Grandes",       "precio": 25.0,  "categorias": ["acompañamiento"]},
        {"nombre": "Limonada Natural",           "precio": 20.0,  "categorias": ["bebida"]},
    ],
    6: [  # El Rincón del Chef
        {"nombre": "Filete Mignon al Vino",      "precio": 185.0, "categorias": ["carnes", "gourmet"]},
        {"nombre": "Langostinos Flameados",      "precio": 165.0, "categorias": ["mariscos", "gourmet"]},
        {"nombre": "Risotto de Champiñones",     "precio": 95.0,  "categorias": ["pasta", "vegetariano"]},
        {"nombre": "Crème Brûlée",              "precio": 55.0,  "categorias": ["postre"]},
        {"nombre": "Vino Tinto Copa",            "precio": 65.0,  "categorias": ["bebida", "vino"]},
    ],
    7: [  # Mariscos del Pacífico
        {"nombre": "Ceviche Mixto",              "precio": 95.0,  "categorias": ["ceviche", "mariscos"]},
        {"nombre": "Camarones al Ajillo",        "precio": 110.0, "categorias": ["camarones", "principal"]},
        {"nombre": "Filete de Pargo Frito",      "precio": 90.0,  "categorias": ["pescado", "principal"]},
        {"nombre": "Sopa de Mariscos",           "precio": 85.0,  "categorias": ["sopa", "mariscos"]},
        {"nombre": "Agua de Coco Natural",       "precio": 30.0,  "categorias": ["bebida"]},
    ],
    8: [  # Veggie Paradise
        {"nombre": "Bowl de Quinoa y Verduras",  "precio": 65.0,  "categorias": ["vegano", "saludable"]},
        {"nombre": "Burger de Garbanzo",         "precio": 60.0,  "categorias": ["vegano", "hamburguesa"]},
        {"nombre": "Tacos de Coliflor BBQ",      "precio": 55.0,  "categorias": ["vegano", "taco"]},
        {"nombre": "Smoothie Verde Detox",       "precio": 35.0,  "categorias": ["bebida", "saludable"]},
        {"nombre": "Cheesecake Vegano",          "precio": 45.0,  "categorias": ["postre", "vegano"]},
    ],
    9: [  # La Churrería Madrileña
        {"nombre": "Churros con Chocolate",      "precio": 35.0,  "categorias": ["churros", "postre"]},
        {"nombre": "Desayuno Español Completo",  "precio": 75.0,  "categorias": ["desayuno", "principal"]},
        {"nombre": "Tortilla Española",          "precio": 55.0,  "categorias": ["español", "huevos"]},
        {"nombre": "Café con Leche",             "precio": 20.0,  "categorias": ["bebida", "café"]},
        {"nombre": "Pan de Cristal con Tomate",  "precio": 30.0,  "categorias": ["aperitivo", "español"]},
    ],
}

NOMBRES = ["Ana", "Carlos", "María", "José", "Laura", "Pedro", "Sofía", "Diego", "Valeria", "Andrés",
           "Camila", "Luis", "Gabriela", "Roberto", "Isabella", "Fernando", "Daniela", "Alejandro", "Paola", "Marcos"]
APELLIDOS = ["García", "López", "Martínez", "González", "Hernández", "Pérez", "Rodríguez", "Flores", "Torres", "Ramírez"]

TAGS_RESENAS = ["excelente_servicio", "sabor_auténtico", "precio_justo", "ambiente_agradable",
                "entrega_rápida", "porciones_grandes", "recomendado", "volveré", "ingredientes_frescos"]


def seed_restaurantes(db):
    """Inserta los 10 restaurantes base."""
    if db.restaurantes.count_documents({}) >= 10:
        print("   ⚠️  Restaurantes ya existen.")
        return list(db.restaurantes.find({}, {"_id": 1}))

    docs = []
    for i, r in enumerate(RESTAURANTES_BASE):
        docs.append({
            "nombre": r["nombre"],
            "descripcion": f"Restaurante especializado en {', '.join(r['categorias'])}. Sabores auténticos en Guatemala City.",
            "telefono": f"+502 {random.randint(2000,9999)}-{random.randint(1000,9999)}",
            "email": f"contacto@{r['nombre'].lower().replace(' ','').replace('á','a').replace('é','e')[:15]}.gt",
            "categorias": r["categorias"],
            "horario": {
                "lunes":     {"apertura": "08:00", "cierre": "21:00"},
                "martes":    {"apertura": "08:00", "cierre": "21:00"},
                "miercoles": {"apertura": "08:00", "cierre": "21:00"},
                "jueves":    {"apertura": "08:00", "cierre": "21:00"},
                "viernes":   {"apertura": "08:00", "cierre": "22:00"},
                "sabado":    {"apertura": "09:00", "cierre": "22:00"},
                "domingo":   {"apertura": "10:00", "cierre": "20:00"},
            },
            "ubicacion": {
                "type": "Point",
                "coordinates": [r["lng"], r["lat"]],
                "direccion": f"{random.randint(1,50)} Av. {random.randint(1,20)}-{random.randint(1,99)}",
                "ciudad": "Guatemala City",
                "pais": "Guatemala"
            },
            "calificacion_promedio": round(random.uniform(3.5, 5.0), 1),
            "total_resenas": random.randint(10, 500),
            "activo": True,
            "imagen_id": None,
            "fecha_registro": datetime.datetime(2023, random.randint(1, 12), random.randint(1, 28))
        })
    result = db.restaurantes.insert_many(docs)
    print(f"   ✅ {len(result.inserted_ids)} restaurantes insertados.")
    return [{"_id": id_} for id_ in result.inserted_ids]


def seed_usuarios(db):
    """Inserta 20 usuarios base."""
    if db.usuarios.count_documents({}) >= 20:
        print("   ⚠️  Usuarios ya existen.")
        return list(db.usuarios.find({}, {"_id": 1}))

    docs = []
    for i in range(20):
        nombre   = random.choice(NOMBRES)
        apellido = random.choice(APELLIDOS)
        docs.append({
            "nombre":   nombre,
            "apellido": apellido,
            "email":    f"{nombre.lower()}.{apellido.lower()}{i}@gmail.com",
            "telefono": f"+502 {random.randint(3000,9999)}-{random.randint(1000,9999)}",
            "direccion_default": {
                "calle":       f"{random.randint(1,30)} Calle {random.randint(1,50)}-{random.randint(1,99)}",
                "zona":        str(random.randint(1, 21)),
                "ciudad":      "Guatemala City",
                "coordinates": [-90.5069 + random.uniform(-0.05, 0.05),
                                  14.6407 + random.uniform(-0.05, 0.05)]
            },
            "historial_pedidos": [],
            "activo":          True,
            "fecha_registro":  datetime.datetime(2023, random.randint(1, 12), random.randint(1, 28))
        })
    result = db.usuarios.insert_many(docs)
    print(f"   ✅ {len(result.inserted_ids)} usuarios insertados.")
    return [{"_id": id_} for id_ in result.inserted_ids]


def seed_menu_items(db):
    """Inserta los menu_items por restaurante."""
    if db.menu_items.count_documents({}) >= 50:
        print("   ⚠️  Menu items ya existen.")
        return list(db.menu_items.find({}, {"_id": 1, "precio": 1, "nombre": 1}))

    restaurantes = list(db.restaurantes.find({}, {"_id": 1}))
    docs = []
    for i, rest in enumerate(restaurantes[:10]):
        items = MENU_POR_RESTAURANTE.get(i, [])
        for item in items:
            docs.append({
                "restaurante_id": rest["_id"],
                "nombre":         item["nombre"],
                "descripcion":    f"Delicioso {item['nombre'].lower()} preparado con ingredientes frescos y de la mejor calidad.",
                "precio":         float(item["precio"]),
                "categorias":     item["categorias"],
                "ingredientes":   ["ingrediente 1", "ingrediente 2", "ingrediente 3"],
                "disponible":     True,
                "tiempo_prep_min": random.randint(10, 45),
                "ventas_total":   random.randint(0, 500),
                "imagen_id":      None,
                "fecha_creacion": datetime.datetime(2023, random.randint(1, 12), random.randint(1, 28))
            })
    result = db.menu_items.insert_many(docs)
    print(f"   ✅ {len(result.inserted_ids)} menu_items insertados.")
    return list(db.menu_items.find({}, {"_id": 1, "precio": 1, "nombre": 1}))


def seed_ordenes(db, n=50000):
    """
    Genera n órdenes históricas con BulkWrite.
    EXACTAMENTE como está definido en Etapa 01, Sección 7.3.
    Usa InsertOne + ordered=False.
    """
    existing = db.ordenes.count_documents({})
    if existing >= n:
        print(f"   ⚠️  Ya existen {existing} órdenes.")
        return existing

    restaurantes = list(db.restaurantes.find({}, {"_id": 1}))
    usuarios     = list(db.usuarios.find({},     {"_id": 1}))
    menu_items   = list(db.menu_items.find({},   {"_id": 1, "precio": 1, "nombre": 1}))
    estados = [
        "pendiente", "confirmado", "en_preparacion",
        "en_camino",  "entregado",  "cancelado"
    ]

    remaining = n - existing
    print(f"   Generando {remaining:,} órdenes con BulkWrite...")

    BATCH_SIZE = 5000
    total_insertadas = 0

    for batch_start in range(0, remaining, BATCH_SIZE):
        batch_n = min(BATCH_SIZE, remaining - batch_start)
        ops = []

        for _ in range(batch_n):
            r = random.choice(restaurantes)["_id"]
            u = random.choice(usuarios)["_id"]
            ni = random.randint(1, 5)

            items = []
            total = 0.0
            for mi in random.sample(menu_items, min(ni, len(menu_items))):
                qty = random.randint(1, 4)
                sub = round(float(mi["precio"]) * qty, 2)
                items.append({
                    "menu_item_id":    mi["_id"],
                    "nombre":          mi["nombre"],
                    "cantidad":        qty,          # int para JSON Schema
                    "precio_unitario": float(mi["precio"]),
                    "subtotal":        float(sub)
                })
                total += sub

            fecha = datetime.datetime(
                2024,
                random.randint(1, 12),
                random.randint(1, 28),
                random.randint(0, 23),
                random.randint(0, 59)
            )

            ops.append(InsertOne({
                "usuario_id":          u,
                "restaurante_id":      r,
                "items":               items,
                "estado":              random.choice(estados),
                "total":               round(total, 2),
                "notas":               "",
                "direccion_entrega": {
                    "calle":       f"{random.randint(1,30)} Calle {random.randint(1,50)}-{random.randint(1,99)}",
                    "zona":        str(random.randint(1, 21)),
                    "ciudad":      "Guatemala City",
                    "coordinates": [-90.5069 + random.uniform(-0.05, 0.05),
                                     14.6407 + random.uniform(-0.05, 0.05)]
                },
                "fecha_creacion":      fecha,
                "fecha_actualizacion": fecha
            }))

        try:
            result = db.ordenes.bulk_write(ops, ordered=False)
            total_insertadas += result.inserted_count
        except BulkWriteError as bwe:
            total_insertadas += bwe.details.get("nInserted", 0)
            print(f"   ⚠️  BulkWriteError en batch: {bwe.details.get('nInserted',0)} insertadas")

        pct = (batch_start + batch_n) / remaining * 100
        print(f"   📦 Batch {batch_start//BATCH_SIZE + 1}: {total_insertadas:,} órdenes insertadas ({pct:.0f}%)")

    print(f"\n   ✅ Total órdenes en BD: {db.ordenes.count_documents({})}")
    return total_insertadas


def seed_resenas(db):
    """Inserta 200 reseñas de ejemplo."""
    if db.resenas.count_documents({}) >= 200:
        print("   ⚠️  Reseñas ya existen.")
        return

    restaurantes = list(db.restaurantes.find({}, {"_id": 1}))
    usuarios     = list(db.usuarios.find({}, {"_id": 1}))
    ordenes      = list(db.ordenes.find({"estado": "entregado"}, {"_id": 1}).limit(200))

    comentarios = [
        "Excelente comida, muy recomendado para toda la familia.",
        "El servicio fue rápido y la comida llegó caliente.",
        "Buena relación calidad-precio, volvería sin duda.",
        "Las porciones son generosas y el sabor es auténtico.",
        "Un lugar con ambiente agradable y comida deliciosa.",
        "El platillo llegó tal como lo describen, muy fresco.",
        "Servicio amable y profesional, lo recomiendo ampliamente.",
        "Calidad consistente, cada vez que pido quedo satisfecho.",
        "Los ingredientes son claramente frescos y de calidad.",
        "Entrega puntual, packaging adecuado y sabor excelente.",
    ]

    docs = []
    for i in range(200):
        r = random.choice(restaurantes)["_id"]
        u = random.choice(usuarios)["_id"]
        orden_ref = random.choice(ordenes)["_id"] if ordenes else None

        doc = {
            "usuario_id":     u,
            "restaurante_id": r,
            "calificacion":   random.randint(1, 5),
            "comentario":     random.choice(comentarios),
            "tags":           random.sample(TAGS_RESENAS, random.randint(1, 4)),
            "util_count":     random.randint(0, 50),
            "fecha":          datetime.datetime(2024, random.randint(1, 12), random.randint(1, 28))
        }
        if orden_ref:
            doc["orden_id"] = orden_ref

        docs.append(doc)

    result = db.resenas.insert_many(docs)
    print(f"   ✅ {len(result.inserted_ids)} reseñas insertadas.")


def seed_all(db=None):
    if db is None:
        db = get_db()

    print("=" * 60)
    print("  Parametric Grill Hub — Seeding de Datos")
    print("=" * 60)

    print("\n── Restaurantes ──────────────────────────────────────────")
    seed_restaurantes(db)

    print("\n── Usuarios ──────────────────────────────────────────────")
    seed_usuarios(db)

    print("\n── Menu Items ────────────────────────────────────────────")
    seed_menu_items(db)

    print("\n── Órdenes (50,000 — BulkWrite) ──────────────────────────")
    seed_ordenes(db, n=50000)

    print("\n── Reseñas ───────────────────────────────────────────────")
    seed_resenas(db)

    print("\n✅ Seeding completo.\n")


if __name__ == "__main__":
    seed_all()
