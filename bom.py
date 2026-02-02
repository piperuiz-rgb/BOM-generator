import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gextia BOM Ultra-Fast", layout="wide")

# --- CARGA DE DATOS CON CACHÉ ---
@st.cache_data
def load_excel(file):
    if os.path.exists(file):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            df.columns = [str(c).strip() for c in df.columns]
            # Limpieza de EANs y relleno de vacíos
            for col in ['EAN', 'Referencia', 'Nombre', 'Color', 'Talla']:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace('.0', '', regex=False).strip()
                    df[col] = df[col].replace('nan', '')
            return df
        except Exception as e:
            st.error(f"Error cargando {file}: {e}")
    return None

df_prendas = load_excel('prendas.xlsx')
df_comp = load_excel('componentes.xlsx')

# --- ESTADO DE SESIÓN ---
if 'mesa_trabajo' not in st.session_state: st.session_state.mesa_trabajo = pd.DataFrame()
if 'bom_final' not in st.session_state: st.session_state.bom_final = pd.DataFrame()

st.title("👗 Gextia BOM: Gestión Visual de Colecciones")

# --- FUNCIONES DE FORMATEO ---
def fmt_prenda(row):
    return f"{row['Referencia']} - {row['Nombre']} ({row['Color']} / {row['Talla']})"

def fmt_comp(row):
    return f"{row['Referencia']} - {row['Nombre']} | {row['Color']} | T: {row.get('Talla', 'U')}"

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🏗️ MESA DE TRABAJO", "🧬 ASIGNACIÓN POR COMPONENTE", "📋 REVISIÓN Y EXPORTACIÓN"])

# --- PESTAÑA 1: MESA DE TRABAJO ---
with tab1:
    if df_prendas is not None:
        st.subheader("Seleccionar Productos Terminados")
        # Creamos una columna de búsqueda combinada
        df_prendas['Display'] = df_prendas.apply(fmt_prenda, axis=1)
        
        opciones_refs = sorted(df_prendas['Referencia'].unique())
        refs_sel = st.multiselect("Filtrar por Referencia Base:", opciones_refs)
        
        if st.button("Añadir a Mesa de Trabajo", type="primary"):
            nuevos = df_prendas[df_prendas['Referencia'].isin(refs_sel)]
            st.session_state.mesa_trabajo = pd.concat([st.session_state.mesa_trabajo, nuevos]).drop_duplicates()
            st.rerun()

        if not st.session_state.mesa_trabajo.empty:
            st.divider()
            st.write(f"📍 Prendas en mesa: {len(st.session_state.mesa_trabajo)}")
            st.dataframe(st.session_state.mesa_trabajo[['Referencia', 'Nombre', 'Color', 'Talla', 'EAN']], 
                         use_container_width=True, hide_index=True)
            if st.button("Vaciar Mesa"):
                st.session_state.mesa_trabajo = pd.DataFrame()
                st.rerun()

# --- PESTAÑA 2: ASIGNACIÓN ---
with tab2:
    if st.session_state.mesa_trabajo.empty or df_comp is None:
        st.info("Configura la mesa de trabajo primero.")
    else:
        st.subheader("1. Selección del Componente")
        # Selector de Componente con Nombre Completo
        df_comp['Display'] = df_comp.apply(fmt_comp, axis=1)
        comp_sel_display = st.selectbox("Buscar Material:", df_comp['Display'].unique())
        row_comp = df_comp[df_comp['Display'] == comp_sel_display].iloc[0]
        
        st.divider()
        st.subheader("2. Destinos en Producto Terminado")
        
        # Selección múltiple de referencias en la mesa
        refs_en_mesa = sorted(st.session_state.mesa_trabajo['Referencia'].unique())
        destinos_refs = st.multiselect("Aplicar a estas prendas:", refs_en_mesa, default=refs_en_mesa)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            modo = st.radio("Filtrar destinos por:", ["Todas las variantes", "Colores específicos", "Tallas específicas"])
        with c2:
            filtros = []
            if modo == "Colores específicos":
                filtros = st.multiselect("Selecciona Colores:", sorted(st.session_state.mesa_trabajo['Color'].unique()))
            elif modo == "Tallas específicas":
                filtros = st.multiselect("Selecciona Tallas:", sorted(st.session_state.mesa_trabajo['Talla'].unique()))
        with c3:
            consumo = st.number_input("Consumo por prenda:", min_value=0.0, value=1.0, format="%.3f")
            ud = row_comp['Unidad de medida']
            st.caption(f"Unidad: {ud}")

        if st.button("🚀 Inyectar Componente a Selección", type="primary"):
            target = st.session_state.mesa_trabajo[st.session_state.mesa_trabajo['Referencia'].isin(destinos_refs)].copy()
            if modo == "Colores específicos" and filtros:
                target = target[target['Color'].isin(filtros)]
            elif modo == "Tallas específicas" and filtros:
                target = target[target['Talla'].isin(filtros)]
            
            # Construcción con metadatos para que en la pestaña 3 se vea todo
            nuevas = pd.DataFrame({
                'Nombre de producto': target['Nombre'],
                'Ref Prenda': target['Referencia'],
                'Col Prenda': target['Color'],
                'Tal Prenda': target['Talla'],
                'Cod Barras Variante': target['EAN'],
                'Cantidad producto final': 1,
                'Tipo de lista de material': 'Fabricación',
                'Subcontratista': '',
                'Ref Comp': row_comp['Referencia'],
                'Nom Comp': row_comp['Nombre'],
                'Col Comp': row_comp['Color'],
                'Tal Comp': row_comp.get('Talla', 'U'),
                'EAN Componente': row_comp['EAN'],
                'Cantidad': consumo,
                'Ud': ud
            })
            st.session_state.bom_final = pd.concat([st.session_state.bom_final, nuevas]).drop_duplicates()
            st.success(f"Asignadas {len(nuevas)} líneas correctamente.")

# --- PESTAÑA 3: REVISIÓN ---
with tab3:
    if not st.session_state.bom_final.empty:
        st.subheader("Edición y Validación Final")
        
        # Ordenamos para que sea legible
        df_view = st.session_state.bom_final.sort_values(by=['Ref Prenda', 'Col Prenda', 'Tal Prenda'])
        
        # TABLA EDITABLE CON TODA LA INFO
        df_editado = st.data_editor(
            df_view,
            column_config={
                "Cantidad": st.column_config.NumberColumn("Consumo", format="%.3f", help="Puedes editar el consumo aquí"),
                "Nombre de producto": st.column_config.Column("Prenda", disabled=True),
                "Ref Prenda": st.column_config.Column("Ref", disabled=True),
                "Col Prenda": st.column_config.Column("Color P.", disabled=True),
                "Tal Prenda": st.column_config.Column("Talla P.", disabled=True),
                "Nom Comp": st.column_config.Column("Material", disabled=True),
                "Col Comp": st.column_config.Column("Color M.", disabled=True),
                "Tal Comp": st.column_config.Column("Talla M.", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic"
        )
        
        st.session_state.bom_final = df_editado

        # Limpieza para exportar solo lo que Odoo/Gextia necesita
        columnas_gextia = ['Nombre de producto', 'Cod Barras Variante', 'Cantidad producto final', 
                           'Tipo de lista de material', 'Subcontratista', 'EAN Componente', 'Cantidad', 'Ud']
        df_export = df_editado[columnas_gextia]

        st.divider()
        c_ex1, c_ex2 = st.columns(2)
        with c_ex1:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False)
            st.download_button("📥 DESCARGAR PARA GEXTIA", output.getvalue(), 
                               "importador_gextia.xlsx", use_container_width=True)
        with c_ex2:
            if st.button("⚠️ BORRAR TODO"):
                st.session_state.bom_final = pd.DataFrame()
                st.rerun()
            
