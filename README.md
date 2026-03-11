# 🍔 Parametric Grill Hub
## CC3089 Base de Datos 2 — UVG — Semestre I 2026

| Campo | Detalle |
|-------|---------|
| Curso | CC3089 Base de Datos 2 |
| Integrante 1 | David Domínguez — Carné: 23712 |
| Integrante 2 | Gabriel Bran — Carné: 23590 |
| Integrante 3 | Luis Padilla — Carné: 23663 |
| Stack | Python 3.12 · PyMongo 4.x · Streamlit · MongoDB Atlas |

---

## Estructura del Proyecto

```
parametric_grill_hub/
├── app.py                          # Frontend Streamlit
├── config.py                       # Conexión MongoDB
├── requirements.txt
├── .env.example                    # Template variables de entorno
│
├── scripts/
│   ├── setup_collections.py        # Paso 1: JSON Schema | Paso 2: Índices | Paso 3: notablescan
│   ├── validate_indexes.py         # explain() COLLSCAN vs IXSCAN → explain_before/after.json
│   └── seed.py                     # 50,000 órdenes con BulkWrite + InsertOne
│
├── crud/
│   ├── create.py                   # crear_restaurante, crear_usuario, crear_menu_item, crear_orden
│   ├── read.py                     # historial_paginado, detalle_orden, cercanos, texto, filtros
│   ├── update.py                   # $set, $mul, $addToSet, $pull, $inc + demo operadores array
│   └── delete.py                   # delete_one, delete_many, soft delete
│
├── aggregations/
│   └── pipelines.py                # Top Restaurantes | Platillos Mes | Ingresos Mensuales | Simples
│
├── gridfs_utils/
│   └── files.py                    # Subir/recuperar imágenes en GridFS
│
└── transactions/
    └── orders.py                   # crear_orden (7 pasos) + cancelar_orden (revertir ventas)
```

---

## Instalación y Ejecución

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd parametric_grill_hub

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu MONGO_URI de Atlas

# 5. Setup inicial (colecciones + índices + notablescan)
python scripts/setup_collections.py

# 6. Seeding (50,000 órdenes con BulkWrite)
python scripts/seed.py

# 7. Validar índices (explain comparativo)
python scripts/validate_indexes.py

# 8. Lanzar frontend Streamlit
streamlit run app.py
```

---

## 5 Colecciones

| Colección | Tipo | JSON Schema | Índices |
|-----------|------|-------------|---------|
| `restaurantes` | Principal | ✅ strict | categorias (multikey), ubicacion (2dsphere) |
| `usuarios` | Principal | — | email (unique) |
| `menu_items` | Referenciada | — | categorias (multikey), texto (weights) |
| `ordenes` | Transaccional | ✅ strict | {usuario_id, fecha}, {restaurante_id, estado} |
| `resenas` | Independiente | ✅ | tags (multikey), comentario (text) |

---

## 9 Índices

| # | Nombre | Tipo | Colección |
|---|--------|------|-----------|
| 1 | `idx_usuarios_email` | Único | usuarios |
| 2 | `idx_ordenes_usuario_fecha` | Compuesto | ordenes |
| 3 | `idx_ordenes_restaurante_estado` | Compuesto | ordenes |
| 4 | `idx_restaurantes_categorias` | Multikey | restaurantes |
| 5 | `idx_menu_categorias` | Multikey | menu_items |
| 6 | `idx_resenas_tags` | Multikey | resenas |
| 7 | `idx_restaurantes_geo` | 2dsphere | restaurantes |
| 8 | `idx_menu_texto` | Text (10/5) | menu_items |
| 9 | `idx_resenas_texto` | Text | resenas |

---

## Transacciones Multi-Documento

### crear_orden() — 7 Pasos
1. `findOne` — verificar usuario activo
2. `findOne` — verificar restaurante activo
3. `find` — verificar disponibilidad de cada item + snapshot precio
4. `insertOne` — crear orden con estado='pendiente'
5. `updateOne $push` — agregar a historial_pedidos del usuario
6. `updateOne $inc` — incrementar ventas_total por cada item
7. `commitTransaction` (automático)

### cancelar_orden() — 3 Pasos
1. Verificar estado in ['pendiente', 'confirmado']
2. `updateOne $set estado='cancelado'`
3. `updateMany $inc ventas_total` (negativo — revierte)

---

## Aggregation Pipelines

### 5.1 Top 10 Restaurantes Mejor Calificados
`$match → $group → $sort → $limit → $lookup → $unwind → $project ($round)`

### 5.2 Platillos Más Vendidos del Mes
`$match (entregado + fecha) → $unwind → $group → $sort → $limit → $lookup × 2 → $unwind × 2 → $project ($round)`

### 5.3 Ingresos Mensuales por Restaurante
`$match → $group ($year/$month/$avg/$sum) → $sort → $lookup → $unwind → $project ($round)`

### readPreference
Todos los pipelines de reporte usan `ReadPreference.SECONDARY_PREFERRED`.

---

## Shard Keys

| Colección | Shard Key | Justificación |
|-----------|-----------|---------------|
| `ordenes` | `{restaurante_id:1, fecha_creacion:1}` | Evita hot spot por restaurante popular |
| `resenas` | `{restaurante_id: 'hashed'}` | Distribución uniforme de escrituras |
| `menu_items` | `{restaurante_id:1}` | Distribución natural por restaurante |
| `usuarios` | `{_id: 'hashed'}` | Inserción uniforme sin patrón predecible |

---

## Seeding — 50,000 Documentos

```python
# Usa BulkWrite con InsertOne, ordered=False (Sección 7.3 Etapa 01)
result = db.ordenes.bulk_write(ops, ordered=False)
# Batches de 5,000 para manejo de memoria
```

---

## Operadores de Array Implementados

| Operador | Uso |
|----------|-----|
| `$push` | Agregar orden al historial_pedidos del usuario |
| `$pull` | Remover item de orden (carrito) |
| `$addToSet` | Agregar tag a reseña sin duplicados |
| `$pop` | Eliminar último item del historial |
| `$elemMatch` | Filtrar órdenes que contienen un item |
| `$size` | Órdenes con exactamente N artículos |
| `$inc` | Incrementar/decrementar ventas_total |
