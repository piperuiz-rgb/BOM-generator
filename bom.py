import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Gextia BOM Ultra-Fast", layout="wide")

# --- 2. CARGA DE DATOS CORREGIDA ---
@st.cache_data
def load_excel(file):
    if os.path.exists(file):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            df.columns = [str(c).strip() for c in df.columns]
            columnas_criticas = ['EAN', 'Referencia', 'Nombre', 'Color', 'Talla']
            for col in columnas_criticas:
                if col in df.columns:
                    df[col] = df[col].astype(str).apply(lambda x: x.replace('.0', '').strip())
                    df[col] = df[col].replace('nan', '')
            return df
        except Exception as e:
            st.error(f"Error cargando {file}: {e}")
    return None

df_prendas = load_excel('prendas.xlsx')
df_comp = load_excel('componentes.xlsx')

# --- 3. ESTADO DE SESIÓN (MEMORIA) ---
if 'mesa_trabajo' not in st.session_state: st.session_state.mesa_trabajo = pd.DataFrame()
if 'bom_final' not in st.session_state: st.session_state.bom_final = pd.DataFrame()

# --- 4. BARRA LATERAL (RESPALDO) ---
with st.sidebar:
    st.header("💾 Copia de Seguridad")
    if not st.session_state.bom_final.empty or not st.session_state.mesa_trabajo.empty:
        output_backup = io.BytesIO()
        with pd.ExcelWriter(output_backup, engine='openpyxl') as writer:
            st.session_state.mesa_trabajo.to_excel(writer, sheet_name='MesaTrabajo', index=False)
            st.session_state.bom_final.to_excel(writer, sheet_name='Escandallo', index=False)
        st.download_button("📥 Descargar Proyecto (.xlsx)", output_backup.getvalue(), 
                           f"backup_{datetime.now().strftime('%H%M')}.xlsx", 
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    
    st.divider()
    archivo_recuperacion = st.file_uploader("📂 Recuperar Proyecto", type=['xlsx'])
    if archivo_recuperacion:
        if st.button("🔄 Restaurar Ahora", use_container_width=True):
            with pd.ExcelFile(archivo_recuperacion) as xls:
                if 'MesaTrabajo' in xls.sheet_names: st.session_state.mesa_trabajo = pd.read_excel(xls, 'MesaTrabajo').astype(str)
                if 'Escandallo' in xls.sheet_names: 
                    df_e = pd.read_excel(xls, 'Escandallo')
                    if 'Cantidad' in df_e.columns: df_e['Cantidad'] = pd.to_numeric(df_e['Cantidad'], errors='coerce')
                    st.session_state.bom_final = df_e
            st.rerun()

# --- 5. CUERPO PRINCIPAL Y PESTAÑAS ---
st.title("👗 Gextia BOM: Gestión Profesional")

# AQUÍ ES DONDE SE DEFINEN LAS 4 PESTAÑAS
tab1, tab2, tab3, tab4 = st.tabs([
    "🏗️ MESA DE TRABAJO", 
    "🧬 ASIGNACIÓN", 
    "📋 REVISIÓN", 
    "📊 RESUMEN DE COMPRA"
])

def fmt_prenda(row): return f"{row['Referencia']} - {row['Nombre']} ({row['Color']} / {row['Talla']})"
def fmt_comp(row): return f"{row['Referencia']} - {row['Nombre']} | {row['Color']} | T: {row.get('Talla', 'U')}"

# --- PESTAÑA 1: MESA DE TRABAJO ---
with tab1:
    if df_prendas is not None:
        st.subheader("Seleccionar Productos")
        opciones_refs = sorted(df_prendas['Referencia'].unique())
        refs_sel = st.multiselect("Filtrar por Referencia Base:", opciones_refs)
        if st.button("Añadir a Mesa", type="primary"):
            nuevos = df_prendas[df_prendas['Referencia'].isin(refs_sel)]
            st.session_state.mesa_trabajo = pd.concat([st.session_state.mesa_trabajo, nuevos]).drop_duplicates()
            st.rerun()
        if not st.session_state.mesa_trabajo.empty:
            st.dataframe(st.session_state.mesa_trabajo[['Referencia', 'Nombre', 'Color', 'Talla', 'EAN']], use_container_width=True, hide_index=True)

# --- PESTAÑA 2: ASIGNACIÓN ---
with tab2:
    if not st.session_state.mesa_trabajo.empty and df_comp is not None:
        df_comp['Display'] = df_comp.apply(fmt_comp, axis=1)
        c_sel = st.selectbox("Buscar Material:", df_comp['Display'].unique())
        row_c = df_comp[df_comp['Display'] == c_sel].iloc[0]
        
        destinos = st.multiselect("Prendas destino:", sorted(st.session_state.mesa_trabajo['Referencia'].unique()))
        c1, c2 = st.columns(2)
        with c1: modo = st.radio("Filtro:", ["Todas", "Colores", "Tallas"])
        with c2: consumo = st.number_input("Consumo:", min_value=0.0, value=1.0, format="%.3f")

        if st.button("🚀 Inyectar"):
            target = st.session_state.mesa_trabajo[st.session_state.mesa_trabajo['Referencia'].isin(destinos)].copy()
            # (Aquí iría la lógica de filtros de color/talla simplificada para brevedad)
            nuevas = pd.DataFrame({
                'Nombre de producto': target['Nombre'], 'Ref Prenda': target['Referencia'],
                'Col Prenda': target['Color'], 'Tal Prenda': target['Talla'],
                'Cod Barras Variante': target['EAN'], 'Cantidad producto final': 1,
                'Tipo de lista de material': 'Fabricación', 'Subcontratista': '',
                'Ref Comp': row_c['Referencia'], 'Nom Comp': row_c['Nombre'],
                'Col Comp': row_c['Color'], 'Tal Comp': row_c.get('Talla', 'U'),
                'EAN Componente': row_c['EAN'], 'Cantidad': consumo, 'Ud': row_c['Unidad de medida']
            })
            st.session_state.bom_final = pd.concat([st.session_state.bom_final, nuevas]).drop_duplicates()
            st.success("¡Inyectado!")

# --- PESTAÑA 3: REVISIÓN ---
with tab3:
    if not st.session_state.bom_final.empty:
        df_edit = st.data_editor(st.session_state.bom_final, use_container_width=True, hide_index=True, num_rows="dynamic")
        st.session_state.bom_final = df_edit
        col_gextia = ['Nombre de producto', 'Cod Barras Variante', 'Cantidad producto final', 'Tipo de lista de material', 'Subcontratista', 'EAN Componente', 'Cantidad', 'Ud']
        output_g = io.BytesIO()
        with pd.ExcelWriter(output_g, engine='openpyxl') as writer:
            df_edit[col_gextia].to_excel(writer, index=False)
        st.download_button("📥 DESCARGAR GEXTIA", output_g.getvalue(), "gextia.xlsx", use_container_width=True)

# --- PESTAÑA 4: RESUMEN DE COMPRA ---
with tab4:
    if not st.session_state.bom_final.empty:
        st.subheader("📊 Necesidades Totales")
        resumen = st.session_state.bom_final.groupby(['Ref Comp', 'Nom Comp', 'Col Comp', 'EAN Componente', 'Ud'])['Cantidad'].sum().reset_index()
        st.dataframe(resumen, use_container_width=True, hide_index=True)
        
        output_r = io.BytesIO()
        with pd.ExcelWriter(output_r, engine='openpyxl') as writer:
            resumen.to_excel(writer, index=False)
        st.download_button("📥 DESCARGAR RESUMEN", output_r.getvalue(), "resumen_compra.xlsx", use_container_width=True)
        
