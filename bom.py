import streamlit as st
import pandas as pd
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gextia BOM Builder", layout="wide")

# Inicializar estados de sesión para agilidad
if 'mesa_trabajo' not in st.session_state: st.session_state.mesa_trabajo = pd.DataFrame()
if 'bom_final' not in st.session_state: st.session_state.bom_final = pd.DataFrame()

st.title("🛠️ Constructor de Listas de Materiales (Gextia)")

# --- SIDEBAR: CARGA DE CATÁLOGOS ---
with st.sidebar:
    st.header("1. Carga de Datos")
    file_prendas = st.file_uploader("Catálogo Productos Terminados", type=['xlsx'])
    file_componentes = st.file_uploader("Catálogo Componentes", type=['xlsx'])
    
    if file_prendas:
        df_prendas = pd.read_excel(file_prendas)
        # Limpieza rápida de EANs
        df_prendas['EAN'] = df_prendas['EAN'].astype(str).str.replace('.0', '', regex=False)
    
    if file_componentes:
        df_comp = pd.read_excel(file_componentes)
        df_comp['EAN'] = df_comp['EAN'].astype(str).str.replace('.0', '', regex=False)

# --- CUERPO PRINCIPAL ---
tab1, tab2, tab3 = st.tabs(["🏗️ Mesa de Trabajo", "🧬 Asignación", "📥 Exportar"])

# PESTAÑA 1: SELECCIÓN DE PRODUCTOS DESTINO
with tab1:
    if file_prendas:
        st.subheader("Selecciona las referencias a escandallar")
        refs_disponibles = sorted(df_prendas['Referencia'].unique())
        seleccion = st.multiselect("Buscar Referencias", refs_disponibles)
        
        if st.button("Añadir a Mesa de Trabajo", type="primary"):
            nuevos = df_prendas[df_prendas['Referencia'].isin(seleccion)]
            st.session_state.mesa_trabajo = pd.concat([st.session_state.mesa_trabajo, nuevos]).drop_duplicates()
            st.success(f"Añadidas {len(nuevos)} variantes a la mesa.")

    if not st.session_state.mesa_trabajo.empty:
        st.write("Variantes en Mesa de Trabajo:")
        st.dataframe(st.session_state.mesa_trabajo, use_container_width=True, hide_index=True)
        if st.button("Limpiar Mesa"):
            st.session_state.mesa_trabajo = pd.DataFrame()
            st.rerun()

# PESTAÑA 2: LÓGICA DE ASIGNACIÓN
with tab2:
    if st.session_state.mesa_trabajo.empty:
        st.warning("Primero añade productos en la 'Mesa de Trabajo'")
    elif not file_componentes:
        st.warning("Carga el catálogo de componentes en la barra lateral")
    else:
        st.subheader("Configuración de Componente")
        col1, col2 = st.columns(2)
        
        with col1:
            ref_c = st.selectbox("Referencia Componente", sorted(df_comp['Referencia'].unique()))
            # Filtramos las variantes del componente elegido
            vars_comp = df_comp[df_comp['Referencia'] == ref_c]
            ean_comp_sel = st.selectbox("EAN Componente (Variante)", vars_comp['EAN'].unique(), 
                                       format_func=lambda x: f"{x} - {vars_comp[vars_comp['EAN']==x]['Color'].values[0]}")
            
            cantidad = st.number_input("Cantidad/Consumo", min_value=0.001, value=1.000, format="%.3f")
            ud_medida = vars_comp[vars_comp['EAN']==ean_comp_sel]['Unidad de medida'].values[0]

        with col2:
            tipo_asig = st.radio("Tipo de Asignación", ["Global", "Específica (Color/Talla)"])
            
            # Filtros dinámicos basados solo en lo que hay en la Mesa de Trabajo
            colores_dest = sorted(st.session_state.mesa_trabajo['Color'].unique())
            tallas_dest = sorted(st.session_state.mesa_trabajo['Talla'].unique())
            
            if tipo_asig == "Específica (Color/Talla)":
                sel_colores = st.multiselect("Aplicar a Colores:", colores_dest)
                sel_tallas = st.multiselect("Aplicar a Tallas:", tallas_dest)
            else:
                st.info("Se aplicará a todas las variantes de la Mesa de Trabajo.")

        if st.button("🔥 Inyectar Componente", type="primary"):
            # Lógica de expansión rápida
            mesa = st.session_state.mesa_trabajo.copy()
            
            if tipo_asig == "Específica (Color/Talla)":
                if sel_colores: mesa = mesa[mesa['Color'].isin(sel_colores)]
                if sel_tallas: mesa = mesa[mesa['Talla'].isin(sel_tallas)]
            
            # Crear las líneas formato Gextia
            nuevas_lineas = pd.DataFrame({
                'Nombre de producto': mesa['Nombre'],
                'Cod Barras Variante': mesa['EAN'],
                'Cantidad producto final': 1,
                'Tipo de lista de material': 'Fabricación',
                'Subcontratista': '',
                'EAN Componente': ean_comp_sel,
                'Cantidad': cantidad,
                'Ud': ud_medida
            })
            
            st.session_state.bom_final = pd.concat([st.session_state.bom_final, nuevas_lineas])
            st.success(f"Inyectadas {len(nuevas_lineas)} líneas al escandallo.")

# PESTAÑA 3: VISTA PREVIA Y EXPORTACIÓN
with tab3:
    if not st.session_state.bom_final.empty:
        st.subheader("Vista Previa del Fichero Gextia")
        st.dataframe(st.session_state.bom_final, use_container_width=True, hide_index=True)
        
        # Generar Excel en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.bom_final.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Lista de Materiales para Gextia",
            data=output.getvalue(),
            file_name=f"BOM_Gextia_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        if st.button("Resetear todo el Escandallo"):
            st.session_state.bom_final = pd.DataFrame()
            st.rerun()
          
