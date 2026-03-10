"""
app.py — Parametric Grill Hub — Frontend Streamlit
Funcionalidades:
  - Crear restaurante (con imagen GridFS)
  - Crear usuario
  - Crear orden (transacción multi-doc)
  - Ver historial de usuario paginado
  - Ejecutar los 3 aggregation pipelines
  - Mostrar imágenes GridFS
  - Validar índices / explain()
  - Demo operadores de array
  - Cancelar orden
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import datetime
from bson import ObjectId
from pymongo.errors import PyMongoError

# ── Imports del proyecto ──────────────────────────────────────────────────────
from config import get_db
from scripts.setup_collections import setup
from scripts.seed import seed_all
from scripts.validate_indexes import validar_indices
from crud.create import crear_restaurante, crear_usuario, crear_menu_item, crear_resena
from crud.read import (historial_usuario_paginado, detalle_orden_completo,
                       restaurantes_cercanos, busqueda_texto_menu,
                       consulta_ordenes_filtradas,
                       listar_restaurantes, listar_menu_restaurante, listar_usuarios,
                       reporte_resenas_enriquecido, ranking_popularidad_menu)
from crud.update import (cambiar_estado_orden, actualizar_precios_restaurante,
                          agregar_tag_resena, quitar_item_orden, demo_operadores_array,
                          demo_push_pop, demo_addtoset_pull, demo_elemmatch, demo_size, demo_inc)
from crud.delete import eliminar_menu_item, eliminar_resenas_usuario, soft_delete_restaurante, eliminar_resena
from transactions.orders import crear_orden, cancelar_orden
from aggregations.pipelines import (ejecutar_top_restaurantes, ejecutar_top_platillos,
                                     ejecutar_ingresos_mensuales, agregaciones_simples,
                                     build_pipeline_top_platillos)
from gridfs_utils.files import subir_imagen_restaurante, recuperar_imagen


# ─────────────────────────────────────────────────────────────────────────────
# Configuración de página
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Parametric Grill Hub",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
  .main-title { font-size: 2.2rem; font-weight: 800; color: #E84545; }
  .section-card {
    background: #1e1e2e;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    border-left: 4px solid #E84545;
  }
  .metric-card {
    background: #2a2a3e;
    border-radius: 8px;
    padding: 12px;
    text-align: center;
  }
  .stButton > button {
    background: #E84545;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
  }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Conexión a BD
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def conectar_bd():
    try:
        db = get_db()
        db.command("ping")
        return db, None
    except Exception as e:
        return None, str(e)

db, error_conexion = conectar_bd()


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────────

def _doc_to_display(doc: dict) -> dict:
    """Convierte ObjectId a str para mostrar en Streamlit."""
    if not doc:
        return {}
    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, datetime.datetime):
            result[k] = v.strftime("%Y-%m-%d %H:%M")
        elif isinstance(v, dict):
            result[k] = str(v)
        elif isinstance(v, list):
            result[k] = str(v)
        else:
            result[k] = v
    return result

def _list_to_df(docs: list) -> pd.DataFrame:
    return pd.DataFrame([_doc_to_display(d) for d in docs])


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Navegación
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<div class="main-title">🍔 Parametric<br>Grill Hub</div>', unsafe_allow_html=True)
    st.markdown("**CC3089 Base de Datos 2 | UVG 2026**")
    st.divider()

    seccion = st.radio("Navegación", [
        "🏠  Dashboard",
        "⚙️  Setup & Seeding",
        "🧬  Estructura Embebida",
        "🍽️  Restaurantes",
        "👤  Usuarios",
        "📋  Órdenes",
        "⭐  Reseñas",
        "📊  Aggregation Pipelines",
        "📑  Multi-Colección",
        "🔍  Índices & explain()",
        "🧩  Operadores de Array",
        "🔎  Búsqueda & Geo",
        "📈  MongoDB Atlas Charts"
    ])

    st.divider()
    if db is not None:
        try:
            n_ordenes = db.ordenes.estimated_document_count()
            n_rest    = db.restaurantes.estimated_document_count()
            n_users   = db.usuarios.estimated_document_count()
            st.metric("Órdenes",      f"{n_ordenes:,}")
            st.metric("Restaurantes", n_rest)
            st.metric("Usuarios",     n_users)
        except:
            pass
    else:
        st.error(f"BD offline: {error_conexion}")


# ─────────────────────────────────────────────────────────────────────────────
# Guard: sin conexión
# ─────────────────────────────────────────────────────────────────────────────
if db is None:
    st.error("No hay conexión a MongoDB. Configura MONGO_URI en tu archivo .env")
    st.code('MONGO_URI=mongodb://localhost:27017/\nDB_NAME=parametric_grill_hub', language="bash")
    st.stop()


# ═════════════════════════════════════════════════════════════════════════════
# 🏠 DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
if seccion.startswith("🏠"):
    st.title("Parametric Grill Hub")
    st.markdown("**Sistema de Gestión de Pedidos y Reseñas — MongoDB Atlas**")
    st.divider()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Órdenes",       f"{db.ordenes.estimated_document_count():,}")
    with col2:
        st.metric("Restaurantes",  db.restaurantes.estimated_document_count())
    with col3:
        st.metric("Usuarios",       db.usuarios.estimated_document_count())
    with col4:
        st.metric("Menu Items",     db.menu_items.estimated_document_count())
    with col5:
        st.metric("Reseñas",        db.resenas.estimated_document_count())

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Órdenes por Estado")
        pipeline_estados = [
            {"$group": {"_id": "$estado", "count": {"$sum": 1}}},
            {"$sort":  {"count": -1}}
        ]
        estados_data = list(db.ordenes.aggregate(pipeline_estados))
        if estados_data:
            df_estados = pd.DataFrame(estados_data).rename(columns={"_id": "Estado", "count": "Cantidad"})
            st.bar_chart(df_estados.set_index("Estado"))

    with col_b:
        st.subheader("Top 5 Restaurantes (Calificación)")
        try:
            top = list(db.resenas.aggregate([
                {"$group": {"_id": "$restaurante_id", "avg": {"$avg": "$calificacion"}, "n": {"$sum": 1}}},
                {"$sort": {"avg": -1}}, {"$limit": 5},
                {"$lookup": {"from": "restaurantes", "localField": "_id", "foreignField": "_id", "as": "r"}},
                {"$unwind": "$r"},
                {"$project": {"Restaurante": "$r.nombre", "Calificación": {"$round": ["$avg", 2]}, "_id": 0}}
            ]))
            if top:
                st.dataframe(pd.DataFrame(top), use_container_width=True)
        except Exception as e:
            st.info(f"Agrega reseñas para ver el top. ({e})")

    st.subheader("Ingresos Mensuales (últimos 6 meses)")
    try:
        ing = list(db.ordenes.aggregate([
            {"$match": {"estado": "entregado"}},
            {"$group": {
                "_id": {"anio": {"$year": "$fecha_creacion"}, "mes": {"$month": "$fecha_creacion"}},
                "ingresos": {"$sum": "$total"}
            }},
            {"$sort": {"_id.anio": -1, "_id.mes": -1}},
            {"$limit": 6}
        ]))
        if ing:
            df_ing = pd.DataFrame([
                {"Periodo": f"{r['_id']['anio']}-{r['_id']['mes']:02d}", "Ingresos Q": r["ingresos"]}
                for r in reversed(ing)
            ])
            st.line_chart(df_ing.set_index("Periodo"))
    except Exception as e:
        st.info(f"Datos insuficientes para gráfico. ({e})")


# ═════════════════════════════════════════════════════════════════════════════
# ⚙️ SETUP & SEEDING
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("⚙️"):
    st.title("Setup & Seeding")
    st.markdown("Inicializa colecciones, índices y datos de prueba.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Configuración Inicial")
        st.markdown("""
        **Paso 1** — Crear colecciones con JSON Schema  
        **Paso 2** — Crear los 9 índices  
        **Paso 3** — Activar `notablescan=1`
        """)
        if st.button("Ejecutar Setup Completo", use_container_width=True):
            with st.spinner("Configurando colecciones e índices..."):
                try:
                    setup(db)
                    st.success("Setup completado.")
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        st.subheader("Seeding de Datos")
        st.markdown("""
        - 10 restaurantes  
        - 20 usuarios  
        - 50 menu items  
        - **50,000 órdenes** (BulkWrite)  
        - 200 reseñas
        """)
        if st.button("Ejecutar Seed Completo", use_container_width=True):
            with st.spinner("Generando 50,000 órdenes... (puede tomar varios minutos)"):
                try:
                    seed_all(db)
                    st.success("Seeding completado.")
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()
    st.subheader("Estado de Colecciones")
    cols_info = []
    for col_name in ["restaurantes", "usuarios", "menu_items", "ordenes", "resenas"]:
        try:
            count = db[col_name].estimated_document_count()
            indices = list(db[col_name].list_indexes())
            cols_info.append({
                "Colección":    col_name,
                "Documentos":   f"{count:,}",
                "Índices":      len(indices),
                "Nombres Idx":  ", ".join(i["name"] for i in indices if i["name"] != "_id_")
            })
        except:
            cols_info.append({"Colección": col_name, "Documentos": "Error", "Índices": 0, "Nombres Idx": ""})
    st.dataframe(pd.DataFrame(cols_info), use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# 🧬 ESTRUCTURA EMBEBIDA (ANATOMÍA)
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("🧬"):
    st.title("Anatomía de Documentos Embebidos")
    st.markdown("""
    En este proyecto, seguimos el principio de **Denormalización Controlada**. 
    Usamos **objetos embebidos (⬛)** para datos que pertenecen lógicamente a una entidad y **referencias (→)** para relaciones entre entidades independientes.
    """)

    tab1, tab2, tab3 = st.tabs(["Restaurantes", "Órdenes", "Usuarios"])

    with tab1:
        st.subheader("Colección: `restaurantes`")
        col_text, col_viz = st.columns([1, 1])
        with col_text:
            st.markdown("""
            **Campos Embebidos:**
            1.  **`ubicacion` (GeoJSON):** Indexado con `2dsphere` para búsquedas espaciales.
            2.  **`horario` (Nested Object):** Almacena la apertura y cierre de cada día de la semana.
            
            **Ventaja:** En una sola lectura de disco obtenemos toda la información necesaria para mostrar el perfil del restaurante, incluyendo si está abierto y dónde está.
            """)
        with col_viz:
            st.code("""
Restaurante (Documento)
├── ubicacion ⬛
│   ├── type: "Point"
│   └── coordinates: [lng, lat]
└── horario ⬛
    ├── lunes: { apertura, cierre }
    ├── ...
    └── domingo: { apertura, cierre }
            """, language="text")
        
        st.divider()
        st.markdown("**Ejemplo Real de `horario` y `ubicacion`:**")
        res = db.restaurantes.find_one()
        if res:
            col_a, col_b = st.columns(2)
            with col_a:
                st.write("**`ubicacion`**")
                st.json(res.get("ubicacion", {}))
            with col_b:
                st.write("**`horario`**")
                st.json(res.get("horario", {}))

    with tab2:
        st.subheader("Colección: `ordenes`")
        st.markdown("""
        Esta es la colección más compleja. Utiliza el **Snapshot Pattern** para garantizar la integridad histórica.
        """)
        
        col_text, col_viz = st.columns([1, 1])
        with col_text:
            st.markdown("""
            **Estructuras clave:**
            1.  **`items` (Array Embebido):** Copiamos el `nombre` y `precio_unitario` del menú. 
                *¿Por qué?* Si el precio del menú sube mañana, esta orden debe mantener el precio original.
            2.  **`direccion_entrega` (Objeto):** Copia de la dirección del usuario al momento de la compra.
            """)
        with col_viz:
            st.code("""
Orden (Documento)
├── items [ ] ⬛ (Snapshot)
│   └── { menu_item_id, nombre, precio_unitario, qty }
└── direccion_entrega ⬛
    └── { calle, zona, ciudad, coordinates }
            """, language="text")

        st.divider()
        st.markdown("**Inspección de Snapshot en Orden:**")
        ord_doc = db.ordenes.find_one()
        if ord_doc:
            st.json({"items_embebidos": ord_doc.get("items", []), "direccion": ord_doc.get("direccion_entrega", {})})

    with tab3:
        st.subheader("Colección: `usuarios`")
        st.markdown("""
        **`direccion_default` ⬛**: Guardada como objeto para agilizar el proceso de Checkout.
        **`historial_pedidos` [ ] →**: Un array de referencias (ObjectIds) que apuntan a la colección `ordenes`.
        """)
        user_doc = db.usuarios.find_one()
        if user_doc:
            st.json({
                "direccion_embebida": user_doc.get("direccion_default", {}),
                "referencias_historial": [str(oid) for oid in user_doc.get("historial_pedidos", [])[:3]] + ["..."]
            })

# ═════════════════════════════════════════════════════════════════════════════
# 🍽️ RESTAURANTES
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("🍽️"):
    st.title("Gestión de Restaurantes")
    tab1, tab2, tab3, tab4 = st.tabs(["Listar", "Crear", "Editar", "Soft Delete"])

    with tab1:
        st.subheader("Restaurantes Registrados")
        filtro_opcion = st.radio(
            "Filtrar por estado:",
            ["Solo Activos", "Solo Inactivos", "Ver Todos"],
            horizontal=True
        )

        # Mapear opción del UI al valor que espera la función
        estado_map = {
            "Solo Activos":   "activos",
            "Solo Inactivos": "inactivos",
            "Ver Todos":      "todos"
        }

        restaurantes = listar_restaurantes(db, filtro_estado=estado_map[filtro_opcion], limite=50)
        if restaurantes:
            rows = []
            for r in restaurantes:
                rows.append({
                    "ID":            str(r["_id"]),
                    "Nombre":        r.get("nombre", ""),
                    "Categorías":    ", ".join(r.get("categorias", [])),
                    "Calificación":  r.get("calificacion_promedio", 0),
                    "Activo":        "Activo" if r.get("activo") else "Inactivo",
                    "Ciudad":        r.get("ubicacion", {}).get("ciudad", ""),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

            # Mostrar imagen GridFS si existe
            sel_id = st.selectbox("Ver imagen de restaurante:", [""] + [str(r["_id"]) for r in restaurantes])
            if sel_id:
                rest = db.restaurantes.find_one({"_id": ObjectId(sel_id)})
                if rest and rest.get("imagen_id"):
                    img_bytes = recuperar_imagen(rest["imagen_id"])
                    if img_bytes:
                        st.image(img_bytes, caption=rest["nombre"], width=300)
                    else:
                        st.info("Imagen no disponible en GridFS.")
                else:
                    st.info("Este restaurante no tiene imagen en GridFS.")
        else:
            st.info("No hay restaurantes. Ejecuta el seeding primero.")

    with tab2:
        st.subheader("Crear Nuevo Restaurante")
        with st.form("form_crear_restaurante"):
            nombre      = st.text_input("Nombre *")
            descripcion = st.text_area("Descripción")
            telefono    = st.text_input("Teléfono")
            email       = st.text_input("Email")
            categorias  = st.text_input("Categorías (separadas por coma) *", "guatemalteca, grill")
            lng         = st.number_input("Longitud *", value=-90.5069, format="%.4f")
            lat         = st.number_input("Latitud *",  value=14.6407,  format="%.4f")
            direccion   = st.text_input("Dirección")
            imagen_file = st.file_uploader("Imagen del restaurante (GridFS)", type=["jpg","jpeg","png"])
            submitted   = st.form_submit_button("Crear Restaurante")

        if submitted:
            if not nombre or not categorias:
                st.error("Nombre y categorías son requeridos.")
            else:
                try:
                    imagen_bytes = imagen_file.read() if imagen_file else None
                    rid = crear_restaurante(db, {
                        "nombre":     nombre,
                        "descripcion": descripcion,
                        "telefono":   telefono,
                        "email":      email,
                        "categorias": [c.strip() for c in categorias.split(",")],
                        "ubicacion":  {
                            "type":        "Point",
                            "coordinates": [lng, lat],
                            "direccion":   direccion,
                            "ciudad":      "Guatemala City",
                            "pais":        "Guatemala"
                        },
                        "activo":     True,
                    }, imagen_bytes=imagen_bytes,
                       imagen_filename=imagen_file.name if imagen_file else "imagen.jpg")
                    st.success(f"Restaurante creado: {rid}")
                except Exception as e:
                    st.error(f"{e}")

    with tab3:
        st.subheader("Actualizar Precios del Menú")
        restaurantes = listar_restaurantes(db)
        if restaurantes:
            opts = {r["nombre"]: r["_id"] for r in restaurantes}
            sel  = st.selectbox("Restaurante:", list(opts.keys()))
            factor = st.slider("Factor de precio ($mul):", 0.5, 2.0, 1.10, 0.05)
            st.info(f"Nuevos precios = precio actual × {factor:.2f}")
            if st.button("Actualizar Precios"):
                n = actualizar_precios_restaurante(db, opts[sel], factor)
                st.success(f"{n} items actualizados con factor {factor}")

    with tab4:
        st.subheader("Soft Delete de Restaurante")
        restaurantes = listar_restaurantes(db, filtro_estado="todos")
        if restaurantes:
            opts = {f"{r['nombre']} ({'activo' if r.get('activo') else 'inactivo'})": r["_id"]
                    for r in restaurantes}
            sel = st.selectbox("Restaurante:", list(opts.keys()))
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Desactivar (Soft Delete)", use_container_width=True):
                    if soft_delete_restaurante(db, opts[sel]):
                        st.success("Restaurante desactivado.")
            with col_b:
                from crud.delete import restaurar_restaurante
                if st.button("Reactivar", use_container_width=True):
                    if restaurar_restaurante(db, opts[sel]):
                        st.success("Restaurante reactivado.")


# ═════════════════════════════════════════════════════════════════════════════
# USUARIOS
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("👤"):
    st.title("Gestión de Usuarios")
    tab1, tab2, tab3 = st.tabs(["Listar", "Crear", "Historial de Órdenes"])

    with tab1:
        usuarios = listar_usuarios(db, limite=50)
        if usuarios:
            rows = [{"ID": str(u["_id"]), "Nombre": f"{u.get('nombre','')} {u.get('apellido','')}",
                     "Email": u.get("email",""), "Activo": "Activo" if u.get("activo") else "Inactivo",
                     "Órdenes": len(u.get("historial_pedidos", []))}
                    for u in usuarios]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("No hay usuarios.")

    with tab2:
        st.subheader("Crear Nuevo Usuario")
        with st.form("form_crear_usuario"):
            nombre   = st.text_input("Nombre *")
            apellido = st.text_input("Apellido")
            email    = st.text_input("Email *")
            telefono = st.text_input("Teléfono")
            calle    = st.text_input("Calle")
            zona     = st.text_input("Zona", "1")
            submitted = st.form_submit_button("Crear Usuario")

        if submitted:
            if not nombre or not email:
                st.error("Nombre y email son requeridos.")
            else:
                uid = crear_usuario(db, {
                    "nombre": nombre, "apellido": apellido,
                    "email": email, "telefono": telefono,
                    "direccion_default": {
                        "calle": calle, "zona": zona,
                        "ciudad": "Guatemala City",
                        "coordinates": [-90.5069, 14.6407]
                    }
                })
                if uid:
                    st.success(f"Usuario creado: {uid}")
                else:
                    st.error("El email ya está registrado (DuplicateKeyError).")

    with tab3:
        st.subheader("Historial de Órdenes Paginado")
        usuarios = listar_usuarios(db)
        usuarios = listar_usuarios(db, limite=50)
        if usuarios:
            opts = {f"{u.get('nombre','')} {u.get('apellido','')} ({u.get('email','')})": u["_id"]
                    for u in usuarios}
            sel      = st.selectbox("Usuario:", list(opts.keys()))
            pagina   = st.number_input("Página", min_value=1, value=1)
            por_pag  = st.selectbox("Por página:", [5, 10, 20, 50], index=1)

            if st.button("Ver Historial"):
                historial = historial_usuario_paginado(db, opts[sel], pagina, por_pag)
                st.metric("Total órdenes", historial["total"])
                st.metric("Páginas",       historial["paginas"])
                if historial["ordenes"]:
                    st.dataframe(_list_to_df(historial["ordenes"]), use_container_width=True)
                else:
                    st.info("Sin órdenes para este usuario.")
        else:
            st.info("Sin usuarios.")


# ═════════════════════════════════════════════════════════════════════════════
# 📋 ÓRDENES
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("📋"):
    st.title("Gestión de Órdenes")
    tab1, tab2, tab3, tab4 = st.tabs(["Listar/Filtrar", "Nueva Orden (Transacción)", "Detalle Completo", "Cancelar"])

    with tab1:
        st.subheader("Órdenes con Filtros y Proyecciones")
        col1, col2 = st.columns(2)
        with col1:
            estado_fil = st.selectbox("Estado:", ["(todos)", "pendiente", "confirmado",
                                                    "en_preparacion", "en_camino", "entregado", "cancelado"])
        with col2:
            pagina = st.number_input("Página", min_value=1, value=1)

        estado_param = None if estado_fil == "(todos)" else estado_fil
        resultado = consulta_ordenes_filtradas(db, estado=estado_param, pagina=pagina, por_pagina=20)
        st.metric("Total encontradas", resultado["total"])
        if resultado["resultados"]:
            st.dataframe(_list_to_df(resultado["resultados"]), use_container_width=True)
        else:
            st.info("Sin resultados.")

    with tab2:
        st.subheader("Nueva Orden — Transacción Multi-Documento")
        st.info("Esta operación ejecuta una transacción ACID de 7 pasos.")

        usuarios     = listar_usuarios(db)
        restaurantes = listar_restaurantes(db)

        if not usuarios or not restaurantes:
            st.warning("Necesitas usuarios y restaurantes. Ejecuta el seeding primero.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                usr_opts = {f"{u.get('nombre','')} {u.get('apellido','')}": u["_id"] for u in usuarios}
                sel_usr  = st.selectbox("Usuario:", list(usr_opts.keys()))
            with col2:
                rst_opts = {r["nombre"]: r["_id"] for r in restaurantes}
                sel_rst  = st.selectbox("Restaurante:", list(rst_opts.keys()))

            menu = listar_menu_restaurante(db, rst_opts[sel_rst])
            if menu:
                st.markdown("**Selecciona items del menú:**")
                items_pedido = []
                for item in menu:
                    col_img, col_name, col_qty = st.columns([0.5, 3, 1])
                    with col_img:
                        if item.get("imagen_id"):
                            img_bytes = recuperar_imagen(item["imagen_id"])
                            if img_bytes:
                                st.image(img_bytes, width=60)
                            else:
                                st.caption("Sin imagen")
                        else:
                            st.caption("Sin imagen")
                    with col_name:
                        st.markdown(f"**{item['nombre']}** — Q{item['precio']:.2f}")
                    with col_qty:
                        qty = st.number_input(f"Qty", min_value=0, max_value=20,
                                               value=0, key=f"qty_{item['_id']}")
                    if qty > 0:
                        items_pedido.append({"menu_item_id": item["_id"], "cantidad": qty})

                if st.button("Crear Orden (Transacción)"):
                    if not items_pedido:
                        st.warning("Selecciona al menos 1 item.")
                    else:
                        try:
                            oid = crear_orden(db, usr_opts[sel_usr], rst_opts[sel_rst], items_pedido)
                            st.success(f"Orden creada exitosamente: {oid}")
                            st.json({"orden_id": str(oid)})
                        except Exception as e:
                            st.error(f"Transacción abortada: {e}")
            else:
                st.info("Este restaurante no tiene items en el menú.")

    with tab3:
        st.subheader("Detalle Completo de Orden")
        st.markdown("Lookup: ordenes → usuarios → restaurantes → menu_items")
        orden_id_str = st.text_input("ID de Orden:")
        if st.button("Ver Detalle") and orden_id_str:
            try:
                detalle = detalle_orden_completo(db, ObjectId(orden_id_str))
                if detalle:
                    # Métricas principales
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Estado", detalle.get("estado", "N/A").upper())
                    col2.metric("Total", f"Q{detalle.get('total', 0):.22}")
                    col3.metric("Usuario", detalle.get("usuario_nombre", "N/A"))
                    col4.metric("Restaurante", detalle.get("restaurante_nombre", "N/A"))

                    # Detalles adicionales
                    st.markdown("---")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Fecha Creación:** {detalle.get('fecha_creacion')}")
                        st.markdown(f"**Usuario Email:** {detalle.get('usuario_email')}")
                    with c2:
                        st.markdown(f"**Ciudad:** {detalle.get('restaurante_ciudad')}")
                        st.markdown(f"**Dirección Entrega:** {detalle.get('direccion_entrega', {}).get('calle', 'N/A')}, Zona {detalle.get('direccion_entrega', {}).get('zona', 'N/A')}")

                    # Tabla de items
                    st.markdown("### Items del Pedido")
                    items_df = pd.DataFrame(detalle.get("items", []))
                    if not items_df.empty:
                        # Renombrar columnas para mejor lectura
                        items_df = items_df.rename(columns={
                            "nombre": "Producto",
                            "cantidad": "Cant.",
                            "precio_unitario": "Precio Unit.",
                            "subtotal": "Subtotal"
                        })
                        st.table(items_df[["Producto", "Cant.", "Precio Unit.", "Subtotal"]])
                    
                    # Mostrar JSON crudo opcionalmente en un expander
                    with st.expander("Ver JSON crudo"):
                        st.json(_doc_to_display(detalle))
                else:
                    st.warning("Orden no encontrada.")
            except Exception as e:
                st.error(f"{e}")

    with tab4:
        st.subheader("Cancelar Orden — Transacción Multi-Documento")
        st.info("Solo se puede cancelar en estado 'pendiente' o 'confirmado'.")
        orden_id_str = st.text_input("ID de Orden a cancelar:")
        if st.button("Cancelar Orden (Transacción)") and orden_id_str:
            try:
                cancelar_orden(db, ObjectId(orden_id_str))
                st.success("Orden cancelada y ventas_total revertidas.")
            except Exception as e:
                st.error(f"{e}")


# ═════════════════════════════════════════════════════════════════════════════
# ⭐ RESEÑAS
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("⭐"):
    st.title("Gestión de Reseñas")
    tab1, tab2, tab3, tab4 = st.tabs(["Listar", "Crear", "Agregar Tag", "Eliminar"])

    with tab1:
        col1, col2 = st.columns([1, 1])
        with col1:
            restaurantes = listar_restaurantes(db)
            opts = {"(todos)": None} | {r["nombre"]: r["_id"] for r in restaurantes}
            sel  = st.selectbox("Filtrar por restaurante:", list(opts.keys()))
        with col2:
            res_id_search = st.text_input("Buscar por ID de Reseña:")

        filtro = {}
        if res_id_search:
            try:
                filtro = {"_id": ObjectId(res_id_search.strip())}
            except:
                st.error("ID no válido")
                filtro = {"_id": None}
        elif opts[sel]:
            filtro = {"restaurante_id": opts[sel]}

        resenas = list(db.resenas.find(filtro).sort("fecha", -1).limit(50))
        if resenas:
            rows = [{"ID": str(r["_id"]), "Calificación": r.get("calificacion"),
                     "Comentario": r.get("comentario","")[:60]+"...",
                     "Tags": ", ".join(r.get("tags",[])),
                     "Fecha": r.get("fecha","").strftime("%Y-%m-%d") if r.get("fecha") else ""}
                    for r in resenas]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("No se encontraron reseñas.")

    with tab2:
        st.subheader("Nueva Reseña")
        usuarios     = listar_usuarios(db)
        restaurantes = listar_restaurantes(db)
        if usuarios and restaurantes:
            usr_opts = {f"{u.get('nombre','')} {u.get('apellido','')}": u["_id"] for u in usuarios}
            rst_opts = {r["nombre"]: r["_id"] for r in restaurantes}
            with st.form("form_crear_resena"):
                sel_usr   = st.selectbox("Usuario:", list(usr_opts.keys()))
                sel_rst   = st.selectbox("Restaurante:", list(rst_opts.keys()))
                calif     = st.slider("Calificación:", 1, 5, 4)
                comentario = st.text_area("Comentario (mín. 5 caracteres):")
                tags_str  = st.text_input("Tags (separados por coma):", "excelente_servicio")
                submitted = st.form_submit_button("Crear Reseña")

            if submitted:
                if len(comentario) < 5:
                    st.error("El comentario debe tener al menos 5 caracteres.")
                else:
                    try:
                        rid = crear_resena(db, {
                            "usuario_id":     usr_opts[sel_usr],
                            "restaurante_id": rst_opts[sel_rst],
                            "calificacion":   calif,
                            "comentario":     comentario,
                            "tags":           [t.strip() for t in tags_str.split(",") if t.strip()]
                        })
                        st.success(f"Reseña creada: {rid}")
                    except Exception as e:
                        st.error(f"{e}")

    with tab3:
        st.subheader("Agregar Tag a Reseña ($addToSet)")
        resena_id_str = st.text_input("ID de Reseña:")
        nuevo_tag     = st.text_input("Nuevo tag:")
        if st.button("Agregar Tag") and resena_id_str and nuevo_tag:
            try:
                agregar_tag_resena(db, ObjectId(resena_id_str), nuevo_tag)
                st.success(f"Tag '{nuevo_tag}' agregado ($addToSet — sin duplicados).")
            except Exception as e:
                st.error(f"{e}")

    with tab4:
        st.subheader("Eliminar Reseña Individual (delete_one)")
        res_del_id = st.text_input("ID de Reseña a eliminar:")
        if st.button("Eliminar Reseña") and res_del_id:
            try:
                if eliminar_resena(db, ObjectId(res_del_id)):
                    st.success(f"Reseña {res_del_id} eliminada correctamente.")
                else:
                    st.warning("No se encontró la reseña.")
            except Exception as e:
                st.error(f"{e}")

        st.divider()
        st.subheader("Eliminar Reseñas de Usuario (delete_many)")
        usuarios = listar_usuarios(db)
        if usuarios:
            usr_opts = {f"{u.get('nombre','')} {u.get('apellido','')} ({u.get('email','')})": u["_id"] for u in usuarios}
            sel_del  = st.selectbox("Usuario:", list(usr_opts.keys()), key="del_usr")
            if st.button("Eliminar todas sus reseñas"):
                n = eliminar_resenas_usuario(db, usr_opts[sel_del])
                st.success(f"{n} reseñas eliminadas.")


# ═════════════════════════════════════════════════════════════════════════════
# 📊 AGGREGATION PIPELINES
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("📊"):
    st.title("Aggregation Pipelines")
    st.markdown("**readPreference: secondaryPreferred** para reportes")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Top 10 Restaurantes",
        "Platillos del Mes",
        "Ingresos Mensuales",
        "Agregaciones Simples"
    ])

    with tab1:
        st.subheader("Top 10 Restaurantes Mejor Calificados")
        st.code("""pipeline = [
  { '$match': { 'calificacion': { '$gte': 1, '$lte': 5 } } },
  { '$group': { '_id': '$restaurante_id', 'promedio': { '$avg': '$calificacion' }, ... } },
  { '$sort': { 'promedio': -1 } }, { '$limit': 10 },
  { '$lookup': { 'from': 'restaurantes', ... } }, { '$unwind': '$restaurante' },
  { '$project': { 'nombre': ..., 'promedio': { '$round': ['$promedio', 2] }, ... } }
]""", language="python")
        if st.button("Ejecutar Pipeline Top Restaurantes"):
            try:
                from pymongo import ReadPreference
                resultado = ejecutar_top_restaurantes(db, ReadPreference.SECONDARY_PREFERRED)
                if resultado:
                    df = pd.DataFrame([_doc_to_display(r) for r in resultado])
                    st.dataframe(df, use_container_width=True)
                    if "promedio" in df.columns and "nombre" in df.columns:
                        st.bar_chart(df.set_index("nombre")["promedio"])
                else:
                    st.info("Sin datos de reseñas suficientes.")
            except Exception as e:
                st.error(f"{e}")

    with tab2:
        st.subheader("Platillos Más Vendidos del Mes")
        st.code("""pipeline = [
  { '$match': { 'estado': 'entregado', 'fecha_creacion': { '$gte': inicio, '$lt': fin } } },
  { '$unwind': '$items' },
  { '$group': { '_id': '$items.menu_item_id', 'vendidos': { '$sum': '$items.cantidad' }, ... } },
  { '$sort': { 'vendidos': -1 } }, { '$limit': 5 },
  { '$lookup': { 'from': 'menu_items', ... } }, { '$unwind': '$menu' },
  { '$lookup': { 'from': 'restaurantes', ... } }, { '$unwind': '$rest' },
  { '$project': { 'platillo': '$menu.nombre', 'restaurante': '$rest.nombre', 'total_vendido': '$vendidos' } }
]""", language="python")
        col1, col2 = st.columns(2)
        with col1:
            año = st.number_input("Año:", min_value=2024, max_value=2026, value=2024)
        with col2:
            mes = st.number_input("Mes:", min_value=1, max_value=12, value=1)

        if st.button("Ejecutar Pipeline Platillos"):
            try:
                from pymongo import ReadPreference
                resultado = ejecutar_top_platillos(db, año=año, mes=mes,
                                                    read_preference=ReadPreference.SECONDARY_PREFERRED)
                if resultado:
                    df = pd.DataFrame([_doc_to_display(r) for r in resultado])
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info(f"Sin órdenes entregadas en {año}-{mes:02d}.")
            except Exception as e:
                st.error(f"{e}")

    with tab3:
        st.subheader("Ingresos Mensuales por Restaurante")
        st.code("""pipeline = [
  { '$match': { 'estado': 'entregado' } },
  { '$group': {
      '_id': { 'rest_id': '$restaurante_id', 'anio': { '$year': '$fecha_creacion' }, 'mes': { '$month': '$fecha_creacion' } },
      'total_mes': { '$sum': '$total' },
      'ticket_promedio': { '$avg': '$total' }
  }},
  { '$sort': { '_id.anio': -1, '_id.mes': -1, 'total_mes': -1 } },
  { '$lookup': { 'from': 'restaurantes', ... } }, { '$unwind': '$r' },
  { '$project': { 'restaurante': '$r.nombre', 'periodo': { '$concat': [...] }, 'total': '$total_mes' } }
]""", language="python")
        if st.button("Ejecutar Pipeline Ingresos"):
            try:
                from pymongo import ReadPreference
                resultado = ejecutar_ingresos_mensuales(db, ReadPreference.SECONDARY_PREFERRED)
                if resultado:
                    df = pd.DataFrame([_doc_to_display(r) for r in resultado]).head(30)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Sin órdenes entregadas.")
            except Exception as e:
                st.error(f"{e}")

    with tab4:
        st.subheader("Agregaciones Simples (Sección 5.4)")
        st.code("""# Comandos directos y optimizados:
db.ordenes.count_documents({'estado': 'pendiente'})
db.menu_items.distinct('categorias')
db.resenas.estimated_document_count()
db.ordenes.aggregate([{ '$match': {'estado': 'entregado'} }, { '$count': 'total' }])""", language="python")
        if st.button("Ejecutar Agregaciones Simples"):
            try:
                simples = agregaciones_simples(db)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Órdenes Pendientes", simples["ordenes_pendientes"])
                with col2:
                    st.metric("Categorías Únicas",  simples["total_categorias"])
                with col3:
                    st.metric("Reseñas (est.)",     simples["total_resenas_estimado"])

                st.metric("Órdenes Entregadas ($count)", simples["ordenes_entregadas"])
                st.markdown("**Categorías distintas:**")
                st.write(simples["categorias_unicas"])
            except Exception as e:
                st.error(f"{e}")


# ═════════════════════════════════════════════════════════════════════════════
# 📑 CONSULTAS AVANZADAS (LOOKUP+)
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("📑"):
    st.title("Consultas Avanzadas (Lookup+)")
    st.markdown("""
    Estas consultas demuestran el uso de **filtros**, **lookups correlacionados**, 
    **proyecciones calculadas**, **ordenamiento** y **paginación**.
    """)

    tab1, tab2 = st.tabs([
        "Reporte de Reseñas Enriquecido",
        "Ranking de Popularidad de Menú"
    ])

    with tab1:
        st.subheader("Reporte: Reseñas → Usuarios → Restaurantes → Órdenes")
        st.markdown("""
        Este reporte une 4 colecciones para mostrar quién escribió la reseña, 
        de qué restaurante y cuál fue el monto de su última orden entregada allí.
        """)

        col1, col2 = st.columns(2)
        with col1:
            min_cal = st.slider("Calificación mínima:", 1, 5, 3, key="cal_adv")
        with col2:
            tag_adv = st.text_input("Filtrar por tag (opcional):", "", key="tag_adv")

        c1, c2 = st.columns(2)
        with c1:
            pag_adv = st.number_input("Página:", min_value=1, value=1, key="pag_adv_1")
        with c2:
            limit_adv = st.selectbox("Por página:", [5, 10, 20, 50], index=1, key="lim_adv_1")

        if st.button("Generar Reporte de Reseñas"):
            try:
                res = reporte_resenas_enriquecido(db, min_calificacion=min_cal, 
                                                 tag=tag_adv if tag_adv else None,
                                                 pagina=pag_adv, por_pagina=limit_adv)
                if res:
                    st.dataframe(pd.DataFrame(res), use_container_width=True)
                else:
                    st.info("No se encontraron resultados con esos filtros.")
            except Exception as e:
                st.error(f"{e}")

    with tab2:
        st.subheader("Ranking: Popularidad de Menú")
        st.markdown("""
        Cruza los platillos con la colección de órdenes para contar en cuántas 
        órdenes *entregadas* aparece cada uno actualmente.
        """)

        col1, col2 = st.columns(2)
        with col1:
            cat_adv = st.text_input("Categoría (opcional):", "", key="cat_adv")
        with col2:
            precio_range = st.slider("Rango de precio:", 0, 500, (0, 500), key="price_adv")

        c1, c2 = st.columns(2)
        with c1:
            pag_adv2 = st.number_input("Página:", min_value=1, value=1, key="pag_adv_2")
        with c2:
            limit_adv2 = st.selectbox("Por página:", [5, 10, 20, 50], index=1, key="lim_adv_2")

        if st.button("Generar Ranking de Popularidad"):
            try:
                res = ranking_popularidad_menu(db, categoria=cat_adv if cat_adv else None,
                                              min_precio=float(precio_range[0]),
                                              max_precio=float(precio_range[1]),
                                              pagina=pag_adv2, por_pagina=limit_adv2)
                if res:
                    st.dataframe(pd.DataFrame(res), use_container_width=True)
                else:
                    st.info("No se encontraron platillos con esos criterios.")
            except Exception as e:
                st.error(f"{e}")


# ═════════════════════════════════════════════════════════════════════════════
# 🔍 ÍNDICES & explain()
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("🔍"):
    st.title("Índices & explain() Comparativo")

    tab1, tab2 = st.tabs(["Índices Creados", "explain() COLLSCAN vs IXSCAN"])

    with tab1:
        st.subheader("Los 9 Índices del Sistema")
        st.markdown("""
        | # | Nombre | Tipo | Colección | Campo(s) |
        |---|--------|------|-----------|----------|
        | 1 | `idx_usuarios_email` | Único | usuarios | email |
        | 2 | `idx_ordenes_usuario_fecha` | Compuesto | ordenes | usuario_id, fecha_creacion |
        | 3 | `idx_ordenes_restaurante_estado` | Compuesto | ordenes | restaurante_id, estado |
        | 4 | `idx_restaurantes_categorias` | Multikey | restaurantes | categorias |
        | 5 | `idx_menu_categorias` | Multikey | menu_items | categorias |
        | 6 | `idx_resenas_tags` | Multikey | resenas | tags |
        | 7 | `idx_restaurantes_geo` | 2dsphere | restaurantes | ubicacion |
        | 8 | `idx_menu_texto` | Text | menu_items | nombre(10), descripcion(5) |
        | 9 | `idx_resenas_texto` | Text | resenas | comentario |
        """)

        st.subheader("Estado Real de los Índices")
        for col_name in ["usuarios", "ordenes", "restaurantes", "menu_items", "resenas"]:
            try:
                indices = list(db[col_name].list_indexes())
                non_default = [i for i in indices if i["name"] != "_id_"]
                if non_default:
                    st.markdown(f"**{col_name}**")
                    for idx in non_default:
                        st.json({
                            "name": idx["name"],
                            "key":  dict(idx["key"]),
                            "unique": idx.get("unique", False),
                            "sparse": idx.get("sparse", False),
                        })
            except Exception as e:
                st.error(f"Error leyendo índices de {col_name}: {e}")

    with tab2:
        st.subheader("explain() Comparativo — COLLSCAN vs IXSCAN")
        st.markdown("""
        **Consulta base:** `db.ordenes.find({'usuario_id': ObjectId(...)}).sort('fecha_creacion', -1)`
        """)

        if st.button("Ejecutar explain() Comparativo"):
            with st.spinner("Ejecutando explain()..."):
                try:
                    resultado = validar_indices(db)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("### Sin Índice (COLLSCAN)")
                        m_antes = resultado["metricas_antes"]
                        st.metric("Stage",              m_antes.get("stage", "N/A"))
                        st.metric("Docs examinados",    str(m_antes.get("totalDocsExamined", "N/A")))
                        st.metric("Tiempo (ms)",        str(m_antes.get("executionTimeMillis", "N/A")))
                    with col2:
                        st.markdown("### Con Índice (IXSCAN)")
                        m_desp = resultado["metricas_despues"]
                        st.metric("Stage",              m_desp.get("stage", "N/A"))
                        st.metric("Docs examinados",    str(m_desp.get("totalDocsExamined", "N/A")))
                        st.metric("Tiempo (ms)",        str(m_desp.get("executionTimeMillis", "N/A")))

                    st.success("Archivos guardados: explain_before.json y explain_after.json")

                    # Mostrar explain raw
                    with st.expander("Ver explain() ANTES (raw)"):
                        from scripts.validate_indexes import _serialize_explain
                        st.json(_serialize_explain(resultado["explain_before"]))
                    with st.expander("Ver explain() DESPUÉS (raw)"):
                        st.json(_serialize_explain(resultado["explain_after"]))

                except Exception as e:
                    st.error(f"{e}")


# ═════════════════════════════════════════════════════════════════════════════
# 🧩 OPERADORES DE ARRAY
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("🧩"):
    st.title("Operadores de Array")
    st.markdown("""
    Pruebas reales de los operadores de array definidos en **Sección 8.1**.
    Puedes ejecutarlos todos juntos o probar uno por uno para ver el impacto exacto en la base de datos.
    """)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Ejecución Rápida")
        if st.button("Ejecutar Demo Completa", use_container_width=True):
            with st.spinner("Ejecutando operadores..."):
                try:
                    resultados = demo_operadores_array(db)
                    st.success("Todos los operadores ejecutados correctamente.")
                    for operador, info in resultados.items():
                        with st.expander(f"Resultado {operador}"):
                            st.json(info)
                except Exception as e:
                    st.error(f"{e}")

    with col2:
        st.subheader("Pruebas Individuales")
        op_seleccionado = st.selectbox("Selecciona un operador para probar:", [
            "$push & $pop (Historial de Usuario)",
            "$addToSet & $pull (Tags de Reseña)",
            "$elemMatch (Filtro de Items en Órdenes)",
            "$size (Filtro por Cantidad de Items)",
            "$inc (Ventas Totales)"
        ])

        if st.button("Probar Seleccionado", use_container_width=True):
            with st.spinner(f"Probando {op_seleccionado}..."):
                try:
                    resultado = {}
                    if op_seleccionado.startswith("$push"):
                        resultado = demo_push_pop(db)
                    elif op_seleccionado.startswith("$addToSet"):
                        resultado = demo_addtoset_pull(db)
                    elif op_seleccionado.startswith("$elemMatch"):
                        resultado = demo_elemmatch(db)
                    elif op_seleccionado.startswith("$size"):
                        resultado = demo_size(db)
                    elif op_seleccionado.startswith("$inc"):
                        resultado = demo_inc(db)

                    st.success(f"Prueba de {op_seleccionado.split(' ')[0]} completada.")
                    st.json(resultado)
                except Exception as e:
                    st.error(f"Error en la prueba: {e}")

    st.divider()
    st.markdown("### Detalle de Operadores")
    st.markdown("""
    | Operador | Caso de uso en Parametric Grill Hub | Descripción |
    |----------|-------------------------------------|-------------|
    | `$push`  | `historial_pedidos` | Agrega un nuevo ID de orden al final del array del usuario. |
    | `$pop`   | `historial_pedidos` | Elimina el último elemento del array (usado aquí para limpieza). |
    | `$addToSet` | `tags` en reseñas | Agrega un tag solo si no existe ya en el array. |
    | `$pull`  | `tags` o `items` | Elimina elementos específicos que coincidan con un criterio. |
    | `$elemMatch` | Búsqueda en `items` | Filtra documentos que tienen al menos un elemento que cumple múltiples condiciones. |
    | `$size`  | Cantidad de `items` | Filtra documentos donde el array tiene exactamente el tamaño especificado. |
    | `$inc`   | `ventas_total` | Incrementa o decrementa valores numéricos (muy común con arrays de transacciones). |
    """)


# ═════════════════════════════════════════════════════════════════════════════
# 🔎 BÚSQUEDA & GEO
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("🔎"):
    st.title("Búsqueda de Texto & Búsqueda Geoespacial")

    tab1, tab2 = st.tabs(["Búsqueda de Texto", "Restaurantes Cercanos ($near)"])

    with tab1:
        st.subheader("Búsqueda Full-Text en Menú ($text + $meta textScore)")
        st.markdown("Índice: `idx_menu_texto` — nombre (weight:10) y descripcion (weight:5)")
        termino = st.text_input("Buscar platillo:", "pollo")
        limite  = st.slider("Resultados:", 1, 20, 10)
        if st.button("Buscar") and termino:
            try:
                resultados = busqueda_texto_menu(db, termino, limite)
                if resultados:
                    rows = [{"Nombre": r.get("nombre"), "Precio": r.get("precio"),
                             "Score": round(r.get("score", 0), 3),
                             "Disponible": r.get("disponible")} for r in resultados]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True)
                else:
                    st.info(f"Sin resultados para '{termino}'.")
            except Exception as e:
                st.error(f"{e}")

    with tab2:
        st.subheader("Restaurantes Cercanos ($near + 2dsphere)")
        st.markdown("Índice: `idx_restaurantes_geo` — GeoJSON Point")
        col1, col2, col3 = st.columns(3)
        with col1:
            lng    = st.number_input("Longitud:", value=-90.5069, format="%.4f")
        with col2:
            lat    = st.number_input("Latitud:", value=14.6407, format="%.4f")
        with col3:
            radio  = st.slider("Radio (metros):", 100, 10000, 2000, 100)

        if st.button("Buscar Cercanos"):
            try:
                cercanos = restaurantes_cercanos(db, lng, lat, radio)
                if cercanos:
                    rows = [{"Nombre": r.get("nombre"),
                             "Categorías": ", ".join(r.get("categorias",[])),
                             "Calificación": r.get("calificacion_promedio", 0)}
                            for r in cercanos]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True)
                    st.success(f"{len(cercanos)} restaurante(s) dentro de {radio}m")
                else:
                    st.info(f"Sin restaurantes dentro de {radio}m.")
            except Exception as e:
                st.error(f"{e}")
                
# ═════════════════════════════════════════════════════════════════════════════
# 📈 MONGO ATLAS CHARTS (EMBEDDED)
# ═════════════════════════════════════════════════════════════════════════════
elif seccion.startswith("📈"):
    st.title("MongoDB Atlas Charts")
    st.markdown("Visualizaciones de negocio embebidas directamente desde **Atlas Charts**.")

    # REEMPLAZA ESTOS LINKS CON TUS PROPIOS LINKS DE ATLAS
    CHARTS = [
        {
            "titulo": "Estado de Órdenes (Tiempo Real)",
            "url": "https://charts.mongodb.com/charts-project-0-sfijcmg/embed/charts?id=950876ef-ba7c-4bad-96a3-c33828008ea2&maxDataAge=14400&theme=dark&autoRefresh=true"
        },
        {
            "titulo": "Ingresos Totales por Mes",
            "url": "https://charts.mongodb.com/charts-project-0-sfijcmg/embed/charts?id=cc9e5453-e568-4353-a83d-d30360645c4b&maxDataAge=14400&theme=dark&autoRefresh=true"
        },
        {
            "titulo": "Top 5 Restaurantes por Venta",
            "url": "https://charts.mongodb.com/charts-project-0-sfijcmg/embed/charts?id=10aaeece-f591-4cc0-af5e-5d49e3262681&maxDataAge=14400&theme=dark&autoRefresh=true"
        },
        {
            "titulo": "Distribucion de rating por tags",
            "url": "https://charts.mongodb.com/charts-project-0-sfijcmg/embed/charts?id=ecb8a6f8-a921-4b43-a9e2-b994d0144f54&maxDataAge=14400&theme=dark&autoRefresh=true"
        },
        {
            "titulo": "Preferencias por Categoría",
            "url": "https://charts.mongodb.com/charts-project-0-sfijcmg/embed/charts?id=e2c9e7d8-fe83-47bb-a2b1-2e4ac72df721&maxDataAge=14400&theme=dark&autoRefresh=true"
        },
        {
            "titulo": "Promedio de calificación por reseña",
            "url": "https://charts.mongodb.com/charts-project-0-sfijcmg/embed/charts?id=0a154d9a-2859-4570-b8f7-aed6e9e3f43e&maxDataAge=14400&theme=dark&autoRefresh=true"
        }
    ]
    for chart in CHARTS:
        with st.container():
            st.subheader(chart["titulo"])
            # Embebemos el Iframe de MongoDB Charts
            st.components.v1.iframe(chart["url"], height=400, scrolling=True)