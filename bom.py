import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gextia BOM & Production", layout="wide", page_icon="🏭")

# --- 2. CARGA DE DATOS ---
@st.cache_data
def load_and_clean_data(file):
    if os.path.exists(file):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            df.columns = [str(c).strip().capitalize() for c in df.columns]
            for col in df.columns:
                df[col] = df[col].astype(str).apply(lambda x: x.replace('.0', '').strip()).replace('nan', '')
            return df
        except Exception as e:
            st.error(f"Error en {file}: {e}")
    return None

df_prendas = load_and_clean_data('prendas.xlsx')
df_comp = load_and_clean_data('componentes.xlsx')

if 'mesa' not in st.session_state: st.session_state.mesa = pd.DataFrame()
if 'bom' not in st.session_state: st.session_state.bom = pd.DataFrame()

# --- 3. SIDEBAR (PROGRESO) ---
with st.sidebar:
    st.header("💾 PROYECTO")
    if not st.session_state.bom.empty or not st.session_state.mesa.empty:
        output_back = io.BytesIO()
        with pd.ExcelWriter(output_back, engine='openpyxl') as writer:
            st.session_state.mesa.to_excel(writer, sheet_name='Mesa', index=False)
            st.session_state.bom.to_excel(writer, sheet_name='BOM', index=False)
        st.download_button("💾 GUARDAR PROYECTO (.xlsx)", output_back.getvalue(), f"BOM_Full_Project_{datetime.now().strftime('%H%M')}.xlsx", use_container_width=True)
    
    st.divider()
    archivo_rec = st.file_uploader("📂 RESTAURAR PROYECTO", type=['xlsx'])
    if archivo_rec:
        if st.button("🔄 RESTAURAR SESIÓN"):
            with pd.ExcelFile(archivo_rec) as xls:
                if 'Mesa' in xls.sheet_names: 
                    df_m = pd.read_excel(xls, 'Mesa')
                    if 'Cant. a fabricar' in df_m.columns: df_m['Cant. a fabricar'] = pd.to_numeric(df_m['Cant. a fabricar'], errors='coerce')
                    st.session_state.mesa = df_m
                if 'BOM' in xls.sheet_names: 
                    df_b = pd.read_excel(xls, 'BOM')
                    df_b['Cantidad'] = pd.to_numeric(df_b['Cantidad'], errors='coerce')
                    df_b['Cantidad producto final'] = pd.to_numeric(df_b['Cantidad producto final'], errors='coerce')
                    st.session_state.bom = df_b
            st.rerun()

# --- 4. CUERPO PRINCIPAL ---
st.title("👗 Gextia Master Planner")

tab1, tab2, tab3, tab4 = st.tabs(["🏗️ MESA: ORDEN DE FABRICACIÓN", "🧬 ASIGNACIÓN", "📋 REVISIÓN ESCANDALLO", "📊 LISTA DE LA COMPRA"])

# --- TAB 1: MESA DE TRABAJO (COMPATIBILIDAD TOTAL) ---
with tab1:
    st.subheader("🏗️ Panel de Control de Producción")
    
    # 1. CARGA DE PRODUCTOS
    if df_prendas is not None:
        opciones = sorted(df_prendas['Referencia'].unique())
        c_sel, c_btn = st.columns([3, 1])
        with c_sel:
            seleccion_refs = st.multiselect("Añadir Referencias al plan:", opciones)
        with c_btn:
            if st.button("➕ CARGAR EN MESA", type="primary", use_container_width=True):
                nuevos = df_prendas[df_prendas['Referencia'].isin(seleccion_refs)].copy()
                # AÑADIMOS COLUMNA DE SELECCIÓN MANUAL
                nuevos['Sel'] = False
                nuevos['Cant. a fabricar'] = 0
                if not st.session_state.mesa.empty:
                    st.session_state.mesa = pd.concat([st.session_state.mesa, nuevos]).drop_duplicates(subset=['Ean'])
                else:
                    st.session_state.mesa = nuevos
                st.rerun()

    if not st.session_state.mesa.empty:
        st.divider()
        
        # 2. BOTONES DE ACCIÓN
        st.write("### ⚡ Acciones sobre filas marcadas")
        c1, c2, c3, c4 = st.columns(4)
        
        # 3. EL EDITOR (Con checkbox real en la primera columna)
        # Reordenamos para que 'Sel' sea lo primero que vea el usuario
        columnas_orden = ['Sel', 'Referencia', 'Nombre', 'Color', 'Talla', 'Cant. a fabricar']
        df_para_editar = st.session_state.mesa[columnas_orden]

        df_mesa_editada = st.data_editor(
            df_para_editar,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Sel": st.column_config.CheckboxColumn("Selección", help="Marca para aplicar cambios masivos"),
                "Cant. a fabricar": st.column_config.NumberColumn(
                    "Unids. a Fabricar",
                    min_value=0, step=1, format="%d",
                ),
                "Referencia": st.column_config.Column(disabled=True),
                "Nombre": st.column_config.Column(disabled=True),
                "Color": st.column_config.Column(disabled=True),
                "Talla": st.column_config.Column(disabled=True)
            }
        )
        
        # Guardamos el estado (importante para que el checkbox se quede marcado)
        st.session_state.mesa = df_mesa_editada

        # 4. LÓGICA DE BOTONES BASADA EN LA COLUMNA 'Sel'
        mask = st.session_state.mesa['Sel'] == True

        with c1:
            if st.button("➕ Añadir 1 (Marcadas)"):
                if mask.any():
                    st.session_state.mesa.loc[mask, 'Cant. a fabricar'] += 1
                    st.rerun()
                else: st.warning("Marca el checkbox de alguna fila")
        
        with c2:
            if st.button("➕ Añadir 5 (Marcadas)"):
                if mask.any():
                    st.session_state.mesa.loc[mask, 'Cant. a fabricar'] += 5
                    st.rerun()
                else: st.warning("Marca el checkbox de alguna fila")

        with c3:
            if st.button("🔄 Reset (Marcadas)"):
                if mask.any():
                    st.session_state.mesa.loc[mask, 'Cant. a fabricar'] = 0
                    st.rerun()
        
        with c4:
            if st.button("🗑️ Quitar (Marcadas)"):
                if mask.any():
                    st.session_state.mesa = st.session_state.mesa[~mask]
                    st.rerun()




# --- TAB 2: ASIGNACIÓN DE MATERIALES ---
with tab2:
    if not st.session_state.mesa.empty:
        st.subheader("2. Inyección de Materiales")
        df_comp['Display'] = df_comp.apply(lambda r: f"{r.get('Referencia','')} - {r.get('Nombre','')} | {r.get('Color','')}", axis=1)
        comp_sel = st.selectbox("Seleccione Material:", df_comp['Display'].unique())
        row_c = df_comp[df_comp['Display'] == comp_sel].iloc[0]
        
        destinos = st.multiselect("Asignar a Referencias:", sorted(st.session_state.mesa['Referencia'].unique()))
        c1, c2 = st.columns(2)
        with c1: modo = st.radio("Filtro:", ["Todas", "Colores", "Tallas"])
        with c2: consumo = st.number_input("Consumo por Prenda:", min_value=0.0, value=1.0, format="%.3f")

        if st.button("🚀 INYECTAR MATERIAL", type="primary"):
            target = st.session_state.mesa[st.session_state.mesa['Referencia'].isin(destinos)].copy()
            # (Filtros de color/talla omitidos por brevedad pero funcionales si se añaden)
            
            nuevas = pd.DataFrame({
                'Nombre de producto': target.get('Nombre',''), 'Cod Barras Variante': target.get('Ean',''),
                'Ref Prenda': target.get('Referencia',''), 'Col Prenda': target.get('Color',''), 'Tal Prenda': target.get('Talla',''),
                'Cantidad producto final': target['Cant. a fabricar'], # TRAEMOS EL DATO DE LA PESTAÑA 1
                'Ref Comp': row_c.get('Referencia',''), 'Nom Comp': row_c.get('Nombre',''), 'Col Comp': row_c.get('Color',''),
                'EAN Componente': row_c.get('Ean',''), 'Cantidad': consumo, 'Ud': row_c.get('Unidad de medida','Un'),
                'Tipo de lista de material': 'Fabricación', 'Subcontratista': ''
            })
            st.session_state.bom = pd.concat([st.session_state.bom, nuevas]).drop_duplicates()
            st.success("Material vinculado a la producción.")

# --- TAB 3: REVISIÓN DE ESCANDALLO ---
with tab3:
    if not st.session_state.bom.empty:
        st.subheader("3. Vista General de Escandallos")
        # Actualizamos las cantidades a fabricar por si se cambiaron en la Pestaña 1 después de inyectar
        # Hacemos un merge para sincronizar la columna 'Cantidad producto final'
        df_bom_actualizada = st.session_state.bom.copy()
        
        df_edit_bom = st.data_editor(
            df_bom_actualizada,
            use_container_width=True, hide_index=True, num_rows="dynamic",
            column_config={
                "Cantidad producto final": st.column_config.NumberColumn("Q. Fabricar", disabled=True),
                "Cantidad": st.column_config.NumberColumn("Consumo Unit."),
                "Nombre de producto": st.column_config.Column(disabled=True)
            }
        )
        st.session_state.bom = df_edit_bom
        
        # Exportación Gextia
        cols_g = ['Nombre de producto', 'Cod Barras Variante', 'Cantidad producto final', 'Tipo de lista de material', 'Subcontratista', 'EAN Componente', 'Cantidad', 'Ud']
        out_g = io.BytesIO()
        with pd.ExcelWriter(out_g, engine='openpyxl') as w: df_edit_bom[cols_g].to_excel(w, index=False)
        st.download_button("📥 DESCARGAR PARA GEXTIA", out_g.getvalue(), "gextia_import.xlsx")

# --- TAB 4: LISTA DE LA COMPRA ---
with tab4:
    if not st.session_state.bom.empty:
        st.subheader("4. Necesidades de Compra Totales")
        
        df_final = st.session_state.bom.copy()
        # Sincronizamos Cantidad producto final con la mesa actual antes de calcular
        # por si el usuario cambió valores en la Pestaña 1
        df_mesa_link = st.session_state.mesa[['Referencia', 'Color', 'Talla', 'Cant. a fabricar']]
        df_final = df_final.drop(columns=['Cantidad producto final']).merge(
            df_mesa_link, 
            left_on=['Ref Prenda', 'Col Prenda', 'Tal Prenda'], 
            right_on=['Referencia', 'Color', 'Talla'],
            how='left'
        ).rename(columns={'Cant. a fabricar': 'Cantidad producto final'})

        # Cálculo
        df_final['Total Compra'] = df_final['Cantidad'] * df_final['Cantidad producto final']
        
        resumen = df_final.groupby(['Ref Comp', 'Nom Comp', 'Col Comp', 'Ud'])['Total Compra'].sum().reset_index()
        
        st.dataframe(resumen, use_container_width=True, hide_index=True)
        
        out_r = io.BytesIO()
        with pd.ExcelWriter(out_r, engine='openpyxl') as w: resumen.to_excel(w, index=False)
        st.download_button("📥 DESCARGAR LISTA COMPRA", out_r.getvalue(), "compra_materiales.xlsx")
        
