"""
scripts/validate_indexes.py — Parametric Grill Hub
Demuestra la diferencia de rendimiento COLLSCAN vs IXSCAN.
Guarda explain_before.json y explain_after.json.
Consulta exacta: db.ordenes.find({'usuario_id': ObjectId(...)}).sort('fecha_creacion', -1)
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure
from bson import ObjectId
from config import get_db

from bson import ObjectId, Timestamp

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _get_sample_usuario_id(db):
    """Obtiene un usuario_id real de la colección de órdenes."""
    orden = db.ordenes.find_one()
    if orden:
        return orden["usuario_id"]
    # fallback
    return ObjectId()


def ejecutar_explain_sin_indice(db, usuario_id):
    resultado = db.command(
        "explain",
        {
            "find":   "ordenes",
            "filter": {"usuario_id": usuario_id},
            "sort":   {"fecha_creacion": -1},
            "hint":   {"$natural": 1}
        },
        verbosity="executionStats"
    )
    return resultado


def ejecutar_explain_con_indice(db, usuario_id):
    resultado = db.command(
        "explain",
        {
            "find":   "ordenes",
            "filter": {"usuario_id": usuario_id},
            "sort":   {"fecha_creacion": -1},
            "hint":   {"usuario_id": 1, "fecha_creacion": -1}
        },
        verbosity="executionStats"
    )
    return resultado

def _serialize_explain(doc):
    if isinstance(doc, dict):
        return {k: _serialize_explain(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [_serialize_explain(i) for i in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, Timestamp):
        return {"t": doc.time, "i": doc.inc}
    elif hasattr(doc, 'isoformat'):
        return doc.isoformat()
    elif isinstance(doc, bytes):
        return doc.hex()
    else:
        return doc


def extraer_metricas(explain_result):
    """Extrae las métricas clave del resultado de explain()."""
    stats = explain_result.get("executionStats", {})
    plan  = explain_result.get("queryPlanner", {}).get("winningPlan", {})

    # Determinar stage principal
    stage = plan.get("stage", "UNKNOWN")
    input_stage = plan.get("inputStage", {}).get("stage", "")
    if input_stage:
        stage = f"{input_stage} → {stage}"

    return {
        "stage":               stage,
        "totalDocsExamined":   stats.get("totalDocsExamined", "N/A"),
        "totalKeysExamined":   stats.get("totalKeysExamined", "N/A"),
        "nReturned":           stats.get("nReturned", "N/A"),
        "executionTimeMillis": stats.get("executionTimeMillis", "N/A"),
    }


def mostrar_comparacion(metricas_antes, metricas_despues):
    """Muestra tabla comparativa de rendimiento."""
    print("\n" + "=" * 65)
    print("  📋 TABLA COMPARATIVA — COLLSCAN vs IXSCAN")
    print("=" * 65)
    print(f"  {'Métrica':<30} {'Sin índice':>12} {'Con índice':>12}")
    print("-" * 65)

    metricas = [
        ("Stage",                "stage"),
        ("Docs examinados",      "totalDocsExamined"),
        ("Keys examinadas",      "totalKeysExamined"),
        ("Docs devueltos",       "nReturned"),
        ("Tiempo ejecución (ms)","executionTimeMillis"),
    ]

    for label, key in metricas:
        v_antes   = str(metricas_antes.get(key,   "N/A"))
        v_despues = str(metricas_despues.get(key, "N/A"))
        print(f"  {label:<30} {v_antes:>12} {v_despues:>12}")

    print("=" * 65)

    # Calcular mejora si los valores son numéricos
    try:
        docs_antes   = int(metricas_antes["totalDocsExamined"])
        docs_despues = int(metricas_despues["totalDocsExamined"])
        tiempo_antes   = int(metricas_antes["executionTimeMillis"])
        tiempo_despues = int(metricas_despues["executionTimeMillis"])

        if docs_despues > 0:
            mejora_docs = docs_antes / docs_despues
            print(f"\n  ✅ Mejora en docs examinados: ×{mejora_docs:,.0f}")
        if tiempo_despues > 0:
            mejora_tiempo = tiempo_antes / tiempo_despues
            print(f"  ✅ Mejora en tiempo:          ×{mejora_tiempo:,.0f}")
    except (TypeError, ValueError, ZeroDivisionError):
        pass

    print()


def validar_indices(db=None):
    if db is None:
        db = get_db()

    print("=" * 65)
    print("  Parametric Grill Hub — Validación de Índices con explain()")
    print("=" * 65)

    # Obtener un usuario_id real
    usuario_id = _get_sample_usuario_id(db)
    print(f"\n🔍 Usando usuario_id: {usuario_id}")
    print(f"📝 Consulta: db.ordenes.find({{'usuario_id': ObjectId(...)}}).sort('fecha_creacion', -1)\n")

    # ── ANTES (COLLSCAN) ──────────────────────────────────────────────────────
    explain_antes = ejecutar_explain_sin_indice(db, usuario_id)
    path_antes = os.path.join(OUTPUT_DIR, "explain_before.json")
    with open(path_antes, "w", encoding="utf-8") as f:
        json.dump(_serialize_explain(explain_antes), f, indent=2, ensure_ascii=False)
    print(f"   💾 Guardado en: {path_antes}")

    # ── DESPUÉS (IXSCAN) ──────────────────────────────────────────────────────
    explain_despues = ejecutar_explain_con_indice(db, usuario_id)
    path_despues = os.path.join(OUTPUT_DIR, "explain_after.json")
    with open(path_despues, "w", encoding="utf-8") as f:
        json.dump(_serialize_explain(explain_despues), f, indent=2, ensure_ascii=False)
    print(f"   💾 Guardado en: {path_despues}")

    # ── COMPARACIÓN ───────────────────────────────────────────────────────────
    metricas_antes   = extraer_metricas(explain_antes)
    metricas_despues = extraer_metricas(explain_despues)
    mostrar_comparacion(metricas_antes, metricas_despues)

    return {
        "explain_before": explain_antes,
        "explain_after":  explain_despues,
        "metricas_antes":   metricas_antes,
        "metricas_despues": metricas_despues,
    }


if __name__ == "__main__":
    validar_indices()
