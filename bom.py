import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gextia BOM Builder", layout="wide")

# --- CARGA AUTOMÁTICA DESDE EXCEL ---
@st.cache_data(show_spinner="Leyendo catálogos Excel...")
def load_excel_data(file_path):
    if os.path.exists(file_path):
        try:
            # Leemos la primera hoja del Excel
            df = pd.read_excel(file_path, engine='openpyxl')
            # Limpieza: quitar espacios en nombres de columnas y convertir EAN a texto limpio
            df.columns = [str(c).strip() for c in df.columns]
            if 'EAN' in df.columns:
                df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
            return df
        except Exception as e:
            st.error(f"Error al leer {file_path}: {e}")
            return None
    return None

# Carga inicial de archivos que están en el mismo repositorio
df_prendas = load_excel_data('prendas.xlsx')
df_comp = load_excel_data('componentes.xlsx')

# Inicializar estados de sesión para el escandallo
if 'mesa_trabajo' not in st.session_state: st.session_state.mesa_trabajo = pd.DataFrame()
if 'bom_final' not in st.session_state: st.session_state.bom_final = pd.DataFrame()

# --- INTERFAZ ---
st.title("🛠️ Gextia BOM Builder (Carga Automática)")

if df_prendas is None or df_comp is None:
    st.warning("⚠️ No se encontraron los archivos 'prendas.xlsx' o 'componentes.xlsx' en el repositorio. Por favor, súbelos para activar la carga automática.")
    # Opción de subida manual por si fallan los de GitHub
    st.subheader("O subir manualmente:")
    manual_p = st.file_uploader("Subir Prendas", type=['xlsx'])
    manual_c = st.file_uploader("Subir Componentes", type=['xlsx'])
    if manual_p: df_prendas = pd.read_excel(manual_p)
    if manual_c: df_comp = pd.read_excel(manual_c)

tab1, tab2, tab3 = st.tabs(["🏗️ MESA DE TRABAJO", "🧬 ASIGNACIÓN", "📥 EXPORTAR"])

# PESTAÑA 1: MESA DE TRABAJO
with tab1:
    if df_prendas is not None:
        st.subheader("Selecciona Modelos")
        refs = sorted(df_prendas['Referencia'].unique())
        seleccion = st.multiselect("Buscar Referencias:", refs)
        
        c1, c2 = st.columns(2)
        if c1.button("Añadir a Mesa", type="primary"):
            nuevos = df_prendas[df_prendas['Referencia'].isin(seleccion)]
            st.session_state.mesa_trabajo = pd.concat([st.session_state.mesa_trabajo, nuevos]).drop_duplicates()
            st.rerun()
        
        if c2.button("Limpiar Mesa"):
            st.session_state.mesa_trabajo = pd.DataFrame()
            st.rerun()

        if not st.session_state.mesa_trabajo.empty:
            st.dataframe(st.session_state.mesa_trabajo, use_container_width=True, hide_index=True)

# PESTAÑA 2: ASIGNACIÓN
with tab2:
    if st.session_state.mesa_trabajo.empty or df_comp is None:
        st.info("Configura la mesa de trabajo y asegúrate de tener el catálogo de componentes.")
    else:
        st.subheader("Configurar Material")
        col_a, col_b = st.columns(2)
        
        with col_a:
            ref_c = st.selectbox("Referencia Componente:", sorted(df_comp['Referencia'].unique()))
            filt_c = df_comp[df_comp['Referencia'] == ref_c]
            ean_c = st.selectbox("EAN Componente:", filt_c['EAN'].unique(),
                                 format_func=lambda x: f"{x} - {filt_c[filt_c['EAN']==x]['Color'].values[0]}")
            consumo = st.number_input("Consumo:", min_value=0.0, value=1.0, format="%.3f")
            # Sacar la unidad de medida del catálogo de componentes
            ud = filt_c[filt_c['EAN'] == ean_c]['Unidad de medida'].values[0]

        with col_b:
            modo = st.radio("Aplicar a:", ["Todo en mesa", "Colores específicos", "Tallas específicas"])
            if modo == "Colores específicos":
                filtros = st.multiselect("Colores:", sorted(st.session_state.mesa_trabajo['Color'].unique()))
            elif modo == "Tallas específicas":
                filtros = st.multiselect("Tallas:", sorted(st.session_state.mesa_trabajo['Talla'].unique()))

        if st.button("🔥 Inyectar Material", type="primary"):
            target = st.session_state.mesa_trabajo.copy()
            if modo == "Colores específicos" and filtros:
                target = target[target['Color'].isin(filtros)]
            elif modo == "Tallas específicas" and filtros:
                target = target[target['Talla'].isin(filtros)]
            
            nuevas_lineas = pd.DataFrame({
                'Nombre de producto': target['Nombre'],
                'Cod Barras Variante': target['EAN'],
                'Cantidad producto final': 1,
                'Tipo de lista de material': 'Fabricación',
                'Subcontratista': '',
                'EAN Componente': ean_c,
                'Cantidad': consumo,
                'Ud': ud
            })
            st.session_state.bom_final = pd.concat([st.session_state.bom_final, nuevas_lineas])
            st.success(f"Añadidas {len(nuevas_lineas)} líneas.")

# PESTAÑA 3: EXPORTAR
with tab3:
    if not st.session_state.bom_final.empty:
        st.dataframe(st.session_state.bom_final, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.bom_final.to_excel(writer, index=False)
        
        st.download_button("📥 DESCARGAR EXCEL GEXTIA", output.getvalue(), 
                           f"import_gextia_{datetime.now().strftime('%d%m_%H%M')}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
            
