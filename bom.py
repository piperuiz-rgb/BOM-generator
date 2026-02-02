import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="Gextia BOM Pro Manager", layout="wide", page_icon="👗")

# Estilo CSS para mejorar la interfaz
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .stDownloadButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE CARGA Y NORMALIZACIÓN ---
@st.cache_data
def load_and_clean_data(file):
    if os.path.exists(file):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            # Normalizar nombres de columnas: Quitar espacios y capitalizar
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            
            # Limpieza de datos en celdas
            for col in df.columns:
                df[col] = df[col].astype(str).apply(lambda x: x.replace('.0', '').strip())
                df[col] = df[col].replace('nan', '')
            return df
        except Exception as e:
            st.error(f"Error crítico en {file}: {e}")
    return None

df_prendas = load_and_clean_data('prendas.xlsx')
df_comp = load_and_clean_data('componentes.xlsx')

# --- 3. GESTIÓN DE ESTADO (PERSISTENCIA) ---
if 'mesa' not in st.session_state: st.session_state.mesa = pd.DataFrame()
if 'bom' not in st.session_state: st.session_state.bom = pd.DataFrame()

# --- 4. BARRA LATERAL: CONTROL DE PROYECTO ---
with st.sidebar:
    st.title("📂 PROYECTO")
    st.info("Gestione el progreso de las 500 variantes aquí.")
    
    # Exportar estado completo
    if not st.session_state.bom.empty or not st.session_state.mesa.empty:
        output_back = io.BytesIO()
        with pd.ExcelWriter(output_back, engine='openpyxl') as writer:
            st.session_state.mesa.to_excel(writer, sheet_name='Mesa', index=False)
            st.session_state.bom.to_excel(writer, sheet_name='Escandallo', index=False)
        st.download_button("💾 DESCARGAR COPIA DE SEGURIDAD", output_back.getvalue(), 
                           f"BOM_Backup_{datetime.now().strftime('%H%M')}.xlsx")
    
    st.divider()
    
    # Importar estado
    archivo_rec = st.file_uploader("📂 RESTAURAR TRABAJO PREVIO", type=['xlsx'])
    if archivo_rec:
        if st.button("🔄 RESTAURAR SESIÓNHORA"):
            with pd.ExcelFile(archivo_rec) as xls:
                if 'Mesa' in xls.sheet_names: st.session_state.mesa = pd.read_excel(xls, 'Mesa').astype(str)
                if 'Escandallo' in xls.sheet_names: 
                    df_b = pd.read_excel(xls, 'Escandallo')
                    if 'Cantidad' in df_b.columns: df_b['Cantidad'] = pd.to_numeric(df_b['Cantidad'], errors='coerce')
                    st.session_state.bom = df_b
            st.rerun()

# --- 5. CUERPO PRINCIPAL ---
st.title("👗 Gextia BOM Professional")
st.caption("Herramienta de gestión masiva de escandallos y necesidades de compra.")

tab1, tab2, tab3, tab4 = st.tabs([
    "🏗️ MESA DE TRABAJO", 
    "🧬 ASIGNACIÓN MASIVA", 
    "📋 REVISIÓN Y EDICIÓN", 
    "📊 RESUMEN DE COMPRA"
])

# Helpers visuales
def fmt_p(row): return f"{row.get('Referencia','')} - {row.get('Nombre','')} ({row.get('Color','')}/{row.get('Talla','')})"
def fmt_c(row): return f"{row.get('Referencia','')} - {row.get('Nombre','')} | {row.get('Color','')}"

# --- PESTAÑA 1: MESA DE TRABAJO ---
with tab1:
    st.subheader("Selección de Productos Terminados")
    if df_prendas is not None:
        col_ref = 'Referencia' if 'Referencia' in df_prendas.columns else df_prendas.columns[0]
        opciones = sorted(df_prendas[col_ref].unique())
        seleccion = st.multiselect("Buscar por Referencia Base:", opciones)
        
        if st.button("➕ AÑADIR A MESA DE TRABAJO", type="primary"):
            nuevos = df_prendas[df_prendas[col_ref].isin(seleccion)]
            st.session_state.mesa = pd.concat([st.session_state.mesa, nuevos]).drop_duplicates()
            st.rerun()

    if not st.session_state.mesa.empty:
        st.write(f"Variantes listas: **{len(st.session_state.mesa)}**")
        # Mostrar solo columnas que existan para evitar KeyErrors
        cols_mostrar = [c for c in ['Referencia', 'Nombre', 'Color', 'Talla', 'Ean'] if c in st.session_state.mesa.columns]
        st.dataframe(st.session_state.mesa[cols_mostrar], use_container_width=True, hide_index=True)
        if st.button("🗑️ VACIAR MESA"):
            st.session_state.mesa = pd.DataFrame()
            st.rerun()

# --- PESTAÑA 2: ASIGNACIÓN ---
with tab2:
    if st.session_state.mesa.empty:
        st.warning("La mesa de trabajo está vacía. Seleccione prendas en la Pestaña 1.")
    else:
        st.subheader("Inyección de Materiales")
        df_comp['Display'] = df_comp.apply(fmt_c, axis=1)
        comp_sel = st.selectbox("Seleccione Componente:", df_comp['Display'].unique())
        row_c = df_comp[df_comp['Display'] == comp_sel].iloc[0]
        
        st.divider()
        refs_mesa = sorted(st.session_state.mesa['Referencia'].unique())
        destinos = st.multiselect("Aplicar a estas Referencias:", refs_mesa, default=refs_mesa)
        
        c1, c2, c3 = st.columns(3)
        with c1: modo = st.radio("Filtro Interno:", ["Todas las variantes", "Colores específicos", "Tallas específicas"])
        with c2: 
            filtros = []
            if modo == "Colores específicos": filtros = st.multiselect("Colores:", sorted(st.session_state.mesa['Color'].unique()))
            if modo == "Tallas específicas": filtros = st.multiselect("Tallas:", sorted(st.session_state.mesa['Talla'].unique()))
        with c3: consumo = st.number_input("Consumo Unitario:", min_value=0.0, value=1.0, format="%.3f")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("🚀 INYECTAR COMPONENTE", type="primary"):
                target = st.session_state.mesa[st.session_state.mesa['Referencia'].isin(destinos)].copy()
                if modo == "Colores específicos" and filtros: target = target[target['Color'].isin(filtros)]
                if modo == "Tallas específicas" and filtros: target = target[target['Talla'].isin(filtros)]
                
                nuevas_lineas = pd.DataFrame({
                    'Nombre de producto': target.get('Nombre', ''), 'Cod Barras Variante': target.get('Ean', ''),
                    'Ref Prenda': target.get('Referencia', ''), 'Col Prenda': target.get('Color', ''), 'Tal Prenda': target.get('Talla', ''),
                    'Cantidad producto final': 1, 'Tipo de lista de material': 'Fabricación', 'Subcontratista': '',
                    'Ref Comp': row_c.get('Referencia', ''), 'Nom Comp': row_c.get('Nombre', ''), 'Col Comp': row_c.get('Color', ''),
                    'EAN Componente': row_c.get('Ean', ''), 'Cantidad': consumo, 'Ud': row_c.get('Unidad de medida', 'Un')
                })
                st.session_state.bom = pd.concat([st.session_state.bom, nuevas_lineas]).drop_duplicates()
                st.success(f"Inyectadas {len(nuevas_lineas)} líneas.")
        with b2:
            if st.button("↩️ DESHACER ÚLTIMA ACCIÓN"):
                if not st.session_state.bom.empty:
                    last_comp = st.session_state.bom['EAN Componente'].iloc[-1]
                    st.session_state.bom = st.session_state.bom[st.session_state.bom['EAN Componente'] != last_comp]
                    st.rerun()

# --- PESTAÑA 3: REVISIÓN ---
with tab3:
    if not st.session_state.bom.empty:
        st.subheader("Edición del Escandallo Final")
        st.caption("💡 Edite consumos directamente o use 'Suprimir' para borrar filas.")
        
        df_edit = st.data_editor(
            st.session_state.bom,
            use_container_width=True, hide_index=True, num_rows="dynamic",
            column_config={
                "Cantidad": st.column_config.NumberColumn("Consumo", format="%.3f"),
                "Nombre de producto": st.column_config.Column(disabled=True),
                "Ref Prenda": st.column_config.Column(disabled=True),
                "Col Prenda": st.column_config.Column(disabled=True),
                "Tal Prenda": st.column_config.Column(disabled=True)
            }
        )
        st.session_state.bom = df_edit

        # Exportar limpio para Gextia
        cols_g = ['Nombre de producto', 'Cod Barras Variante', 'Cantidad producto final', 
                  'Tipo de lista de material', 'Subcontratista', 'EAN Componente', 'Cantidad', 'Ud']
        out_g = io.BytesIO()
        with pd.ExcelWriter(out_g, engine='openpyxl') as w: df_edit[cols_g].to_excel(w, index=False)
        st.download_button("📥 DESCARGAR PARA GEXTIA (.xlsx)", out_g.getvalue(), "import_gextia.xlsx")

# --- PESTAÑA 4: COMPRAS ---
with tab4:
    if not st.session_state.bom.empty:
        st.subheader("Resumen Consolidado de Necesidades")
        resumen = st.session_state.bom.groupby(['Ref Comp', 'Nom Comp', 'Col Comp', 'Ud'])['Cantidad'].sum().reset_index()
        resumen = resumen.rename(columns={'Cantidad': 'Total Necesario'})
        st.dataframe(resumen, use_container_width=True, hide_index=True)
        
        out_r = io.BytesIO()
        with pd.ExcelWriter(out_r, engine='openpyxl') as w: resumen.to_excel(w, index=False)
        st.download_button("📥 DESCARGAR LISTA DE COMPRA", out_r.getvalue(), "necesidades_material.xlsx")
                
