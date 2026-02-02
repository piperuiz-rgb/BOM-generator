import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gextia BOM Pro", layout="wide")

# --- 2. CARGA DE DATOS ---
@st.cache_data
def load_excel(file):
    if os.path.exists(file):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            df.columns = [str(c).strip() for c in df.columns]
            columnas_criticas = ['EAN', 'Referencia', 'Nombre', 'Color', 'Talla']
            for col in columnas_criticas:
                if col in df.columns:
                    df[col] = df[col].astype(str).apply(lambda x: x.replace('.0', '').strip()).replace('nan', '')
            return df
        except Exception as e:
            st.error(f"Error: {e}")
    return None

df_prendas = load_excel('prendas.xlsx')
df_comp = load_excel('componentes.xlsx')

# --- 3. ESTADO DE SESIÓN ---
if 'mesa_trabajo' not in st.session_state: st.session_state.mesa_trabajo = pd.DataFrame()
if 'bom_final' not in st.session_state: st.session_state.bom_final = pd.DataFrame()

# --- 4. SIDEBAR (PROGRESO) ---
with st.sidebar:
    st.header("💾 PROYECTO")
    if not st.session_state.bom_final.empty or not st.session_state.mesa_trabajo.empty:
        output_backup = io.BytesIO()
        with pd.ExcelWriter(output_backup, engine='openpyxl') as writer:
            st.session_state.mesa_trabajo.to_excel(writer, sheet_name='Mesa', index=False)
            st.session_state.bom_final.to_excel(writer, sheet_name='BOM', index=False)
        st.download_button("📥 GUARDAR TODO (.xlsx)", output_backup.getvalue(), "proyecto.xlsx", use_container_width=True)
    
    st.divider()
    archivo = st.file_uploader("📂 CARGAR PROYECTO", type=['xlsx'])
    if archivo:
        if st.button("🔄 RESTAURAR"):
            with pd.ExcelFile(archivo) as xls:
                if 'Mesa' in xls.sheet_names: st.session_state.mesa_trabajo = pd.read_excel(xls, 'Mesa').astype(str)
                if 'BOM' in xls.sheet_names:
                    df_b = pd.read_excel(xls, 'BOM')
                    if 'Cantidad' in df_b.columns: df_b['Cantidad'] = pd.to_numeric(df_b['Cantidad'], errors='coerce')
                    st.session_state.bom_final = df_b
            st.rerun()

# --- 5. TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🏗️ MESA DE TRABAJO", "🧬 ASIGNACIÓN", "📋 REVISIÓN", "📊 COMPRAS"])

def fmt_p(row): return f"{row['Referencia']} - {row['Nombre']} ({row['Color']}/{row['Talla']})"
def fmt_c(row): return f"{row['Referencia']} - {row['Nombre']} | {row['Color']}"

# --- TAB 1: MESA ---
with tab1:
    if df_prendas is not None:
        refs = sorted(df_prendas['Referencia'].unique())
        sel = st.multiselect("Selecciona Referencias:", refs)
        if st.button("Añadir", type="primary"):
            nuevos = df_prendas[df_prendas['Referencia'].isin(sel)]
            st.session_state.mesa_trabajo = pd.concat([st.session_state.mesa_trabajo, nuevos]).drop_duplicates()
            st.rerun()
        st.dataframe(st.session_state.mesa_trabajo[['Referencia','Nombre','Color','Talla']], use_container_width=True, hide_index=True)

# --- TAB 2: ASIGNACIÓN ---
with tab2:
    if not st.session_state.mesa_trabajo.empty and df_comp is not None:
        df_comp['Disp'] = df_comp.apply(fmt_c, axis=1)
        c_sel = st.selectbox("Material:", df_comp['Disp'].unique())
        row_c = df_comp[df_comp['Disp'] == c_sel].iloc[0]
        
        destinos = st.multiselect("Prendas:", sorted(st.session_state.mesa_trabajo['Referencia'].unique()))
        c1, c2 = st.columns(2)
        with c1: modo = st.radio("Filtro:", ["Todas", "Colores", "Tallas"])
        with c2: consumo = st.number_input("Consumo:", min_value=0.0, value=1.0, format="%.3f")

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("🚀 INYECTAR", use_container_width=True, type="primary"):
                target = st.session_state.mesa_trabajo[st.session_state.mesa_trabajo['Referencia'].isin(destinos)].copy()
                # Filtrado por colores/tallas si es necesario (simplificado)
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
                st.success("¡Hecho!")
        with col_b2:
            if st.button("↩️ DESHACER ÚLTIMA", use_container_width=True):
                if not st.session_state.bom_final.empty:
                    last_ean = st.session_state.bom_final['EAN Componente'].iloc[-1]
                    st.session_state.bom_final = st.session_state.bom_final[st.session_state.bom_final['EAN Componente'] != last_ean]
                    st.rerun()

# --- TAB 3: REVISIÓN ---
with tab3:
    if not st.session_state.bom_final.empty:
        st.info("Selecciona una fila y pulsa 'Suprimir' para borrarla.")
        df_edit = st.data_editor(st.session_state.bom_final, use_container_width=True, hide_index=True, num_rows="dynamic")
        st.session_state.bom_final = df_edit
        
        col_g = ['Nombre de producto', 'Cod Barras Variante', 'Cantidad producto final', 'Tipo de lista de material', 'Subcontratista', 'EAN Componente', 'Cantidad', 'Ud']
        out_g = io.BytesIO()
        with pd.ExcelWriter(out_g, engine='openpyxl') as w: df_edit[col_g].to_excel(w, index=False)
        st.download_button("📥 EXCEL GEXTIA", out_g.getvalue(), "gextia.xlsx", use_container_width=True)

# --- TAB 4: COMPRAS ---
with tab4:
    if not st.session_state.bom_final.empty:
        res = st.session_state.bom_final.groupby(['Ref Comp', 'Nom Comp', 'Col Comp', 'Ud'])['Cantidad'].sum().reset_index()
        st.dataframe(res.rename(columns={'Cantidad': 'Total'}), use_container_width=True, hide_index=True)
        out_r = io.BytesIO()
        with pd.ExcelWriter(out_r, engine='openpyxl') as w: res.to_excel(w, index=False)
        st.download_button("📥 LISTA COMPRAS", out_r.getvalue(), "compras.xlsx", use_container_width=True)
                         
