"""
aggregations/pipelines.py — Parametric Grill Hub
Aggregation Pipelines (30 pts) — EXACTAMENTE como están en Etapa 01:

  5.1 pipeline_top_restaurantes   — Top 10 restaurantes mejor calificados
  5.2 pipeline_top_platillos      — Platillos más vendidos del mes
  5.3 pipeline_ingresos           — Ingresos mensuales por restaurante
  5.4 Agregaciones simples        — count_documents, distinct, estimated_document_count, $count
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import datetime
from config import get_db


# ──────────────────────────────────────────────────────────────────────────────
# 5.1 Top 10 Restaurantes Mejor Calificados
# ──────────────────────────────────────────────────────────────────────────────

pipeline_top_restaurantes = [
    # 1. Solo reseñas con calificación válida
    {"$match": {"calificacion": {"$gte": 1, "$lte": 5}}},

    # 2. Agrupar por restaurante y calcular métricas
    {"$group": {
        "_id":             "$restaurante_id",
        "promedio":        {"$avg": "$calificacion"},
        "total_resenas":   {"$sum": 1},
        "calificacion_max": {"$max": "$calificacion"}
    }},

    # 3. Ordenar de mejor a peor
    {"$sort": {"promedio": -1, "total_resenas": -1}},
    {"$limit": 10},

    # 4. Enriquecer con datos del restaurante
    {"$lookup": {
        "from":         "restaurantes",
        "localField":   "_id",
        "foreignField": "_id",
        "as":           "restaurante"
    }},
    {"$unwind": "$restaurante"},

    # 5. Proyección final
    {"$project": {
        "nombre":        "$restaurante.nombre",
        "ciudad":        "$restaurante.ubicacion.ciudad",
        "promedio":      {"$round": ["$promedio", 2]},
        "total_resenas": 1
    }}
]


# ──────────────────────────────────────────────────────────────────────────────
# 5.2 Platillos Más Vendidos del Mes
# ──────────────────────────────────────────────────────────────────────────────

def build_pipeline_top_platillos(año: int = None, mes: int = None):
    """
    Construye el pipeline de platillos más vendidos del mes dado.
    Si no se especifica, usa el mes actual.
    """
    hoy = datetime.datetime.utcnow()
    año = año or hoy.year
    mes = mes or hoy.month
    inicio_mes = datetime.datetime(año, mes, 1)

    return [
        {"$match": {
            "estado":         "entregado",
            "fecha_creacion": {"$gte": inicio_mes}
        }},
        {"$unwind": "$items"},
        {"$group": {
            "_id":           "$items.menu_item_id",
            "total_vendido": {"$sum": "$items.cantidad"},
            "ingreso_total": {"$sum": "$items.subtotal"}
        }},
        {"$sort":  {"total_vendido": -1}},
        {"$limit": 5},

        # Lookup menu_items
        {"$lookup": {
            "from":         "menu_items",
            "localField":   "_id",
            "foreignField": "_id",
            "as":           "articulo"
        }},
        {"$unwind": "$articulo"},

        # Lookup restaurantes
        {"$lookup": {
            "from":         "restaurantes",
            "localField":   "articulo.restaurante_id",
            "foreignField": "_id",
            "as":           "restaurante"
        }},
        {"$unwind": "$restaurante"},

        {"$project": {
            "platillo":      "$articulo.nombre",
            "restaurante":   "$restaurante.nombre",
            "total_vendido": 1,
            "ingreso_total": {"$round": ["$ingreso_total", 2]}
        }}
    ]

# Instancia con mes actual (también se puede llamar con parámetros)
pipeline_top_platillos = build_pipeline_top_platillos()


# ──────────────────────────────────────────────────────────────────────────────
# 5.3 Reporte de Ingresos Mensuales por Restaurante
# ──────────────────────────────────────────────────────────────────────────────

pipeline_ingresos = [
    {"$match": {"estado": "entregado"}},
    {"$group": {
        "_id": {
            "restaurante_id": "$restaurante_id",
            "anio":           {"$year":  "$fecha_creacion"},
            "mes":            {"$month": "$fecha_creacion"}
        },
        "ingresos_totales": {"$sum":  "$total"},
        "total_ordenes":    {"$sum":  1},
        "ticket_promedio":  {"$avg":  "$total"}
    }},
    {"$sort": {
        "_id.anio": -1, "_id.mes": -1, "ingresos_totales": -1
    }},
    {"$lookup": {
        "from":         "restaurantes",
        "localField":   "_id.restaurante_id",
        "foreignField": "_id",
        "as":           "restaurante"
    }},
    {"$unwind": "$restaurante"},
    {"$project": {
        "restaurante":      "$restaurante.nombre",
        "anio":             "$_id.anio",
        "mes":              "$_id.mes",
        "ingresos_totales": {"$round": ["$ingresos_totales", 2]},
        "total_ordenes":    1,
        "ticket_promedio":  {"$round": ["$ticket_promedio", 2]}
    }}
]


# ──────────────────────────────────────────────────────────────────────────────
# Funciones de ejecución
# ──────────────────────────────────────────────────────────────────────────────

def ejecutar_top_restaurantes(db, read_preference=None) -> list:
    """Ejecuta pipeline Top 10 Restaurantes. Usa secondaryPreferred para reportes."""
    coll = db.resenas
    if read_preference:
        coll = db.get_collection("resenas", read_preference=read_preference)
    resultado = list(coll.aggregate(pipeline_top_restaurantes))
    print(f"✅ Top Restaurantes: {len(resultado)} resultados")
    return resultado


def ejecutar_top_platillos(db, año: int = None, mes: int = None,
                            read_preference=None) -> list:
    """Ejecuta pipeline Platillos Más Vendidos del Mes."""
    pipeline = build_pipeline_top_platillos(año, mes)
    coll = db.ordenes
    if read_preference:
        coll = db.get_collection("ordenes", read_preference=read_preference)
    resultado = list(coll.aggregate(pipeline))
    print(f"✅ Top Platillos: {len(resultado)} resultados")
    return resultado


def ejecutar_ingresos_mensuales(db, read_preference=None) -> list:
    """Ejecuta pipeline Ingresos Mensuales por Restaurante."""
    coll = db.ordenes
    if read_preference:
        coll = db.get_collection("ordenes", read_preference=read_preference)
    resultado = list(coll.aggregate(pipeline_ingresos))
    print(f"✅ Ingresos Mensuales: {len(resultado)} resultados")
    return resultado


# ──────────────────────────────────────────────────────────────────────────────
# 5.4 Agregaciones Simples
# ──────────────────────────────────────────────────────────────────────────────

def agregaciones_simples(db) -> dict:
    """
    Ejecuta las 4 agregaciones simples definidas en Etapa 01, Sección 5.4.
    """

    # 1. count_documents — órdenes pendientes
    pendientes = db.ordenes.count_documents({"estado": "pendiente"})
    print(f"✅ count_documents (pendientes): {pendientes}")

    # 2. distinct — categorías únicas de restaurantes
    categorias = db.restaurantes.distinct("categorias")
    print(f"✅ distinct (categorias restaurantes): {len(categorias)} únicas")

    # 3. estimated_document_count — conteo rápido para dashboard
    total_resenas = db.resenas.estimated_document_count()
    print(f"✅ estimated_document_count (reseñas): {total_resenas}")

    # 4. $count en pipeline — total órdenes entregadas
    result_count = list(db.ordenes.aggregate([
        {"$match": {"estado": "entregado"}},
        {"$count": "total_entregadas"}
    ]))
    total_entregadas = result_count[0]["total_entregadas"] if result_count else 0
    print(f"✅ $count pipeline (entregadas): {total_entregadas}")

    return {
        "ordenes_pendientes":           pendientes,
        "categorias_unicas":            categorias,
        "total_categorias":             len(categorias),
        "total_resenas_estimado":       total_resenas,
        "ordenes_entregadas":           total_entregadas,
    }


def ejecutar_todos_los_pipelines(db) -> dict:
    """
    Ejecuta todos los pipelines y agregaciones simples.
    Usa readPreference secondaryPreferred para reportes.
    """
    from pymongo import ReadPreference

    print("\n" + "=" * 60)
    print("  Parametric Grill Hub — Aggregation Pipelines")
    print("=" * 60)

    print("\n── 5.1 Top 10 Restaurantes Mejor Calificados ────────────")
    top_restaurantes = ejecutar_top_restaurantes(
        db,
        read_preference=ReadPreference.SECONDARY_PREFERRED
    )

    print("\n── 5.2 Platillos Más Vendidos del Mes ───────────────────")
    top_platillos = ejecutar_top_platillos(
        db,
        read_preference=ReadPreference.SECONDARY_PREFERRED
    )

    print("\n── 5.3 Ingresos Mensuales por Restaurante ───────────────")
    ingresos = ejecutar_ingresos_mensuales(
        db,
        read_preference=ReadPreference.SECONDARY_PREFERRED
    )

    print("\n── 5.4 Agregaciones Simples ──────────────────────────────")
    simples = agregaciones_simples(db)

    return {
        "top_restaurantes": top_restaurantes,
        "top_platillos":    top_platillos,
        "ingresos":         ingresos,
        "simples":          simples,
    }


if __name__ == "__main__":
    db = get_db()
    ejecutar_todos_los_pipelines(db)
