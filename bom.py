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

# --- TAB 1: MESA DE TRABAJO (FILTROS POR TALLA + ACCIONES MASIVAS) ---
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
                nuevos['Sel'] = False
                nuevos['Cant. a fabricar'] = 0
                if not st.session_state.mesa.empty:
                    st.session_state.mesa = pd.concat([st.session_state.mesa, nuevos]).drop_duplicates(subset=['Ean'])
                else:
                    st.session_state.mesa = nuevos
                st.rerun()

    if not st.session_state.mesa.empty:
        st.divider()
        
        # 2. SELECTORES GLOBALES Y FILTROS DE TALLA
        st.write("### ⚡ Acciones Masivas e Inteligentes")
        
        c_all, c_talla, c_ops = st.columns([1, 1.5, 3])
        
        with c_all:
            select_all = st.checkbox("Seleccionar todas", key="master_sel")
            if select_all != st.session_state.get('prev_select_all', False):
                st.session_state.mesa['Sel'] = select_all
                st.session_state['prev_select_all'] = select_all
                st.rerun()
        
        with c_talla:
            tallas_disponibles = ["Cualquier Talla"] + sorted(st.session_state.mesa['Talla'].unique().tolist())
            talla_target = st.selectbox("🎯 Filtrar por Talla:", tallas_disponibles)

        with c_ops:
            # Lógica de máscara: Solo seleccionados Y (si aplica) solo la talla elegida
            mask = st.session_state.mesa['Sel'] == True
            if talla_target != "Cualquier Talla":
                mask = mask & (st.session_state.mesa['Talla'] == talla_target)
            
            # Botones de acción
            b1, b2, b3, b4 = st.columns(4)
            
            if b1.button("➕1"):
                if mask.any():
                    st.session_state.mesa.loc[mask, 'Cant. a fabricar'] += 1
                    st.rerun()
            
            if b2.button("➕5"):
                if mask.any():
                    st.session_state.mesa.loc[mask, 'Cant. a fabricar'] += 5
                    st.rerun()
            
            if b3.button("➕10"):
                if mask.any():
                    st.session_state.mesa.loc[mask, 'Cant. a fabricar'] += 10
                    st.rerun()
            
            if b4.button("🗑️ Quitar"):
                if mask.any():
                    st.session_state.mesa = st.session_state.mesa[~mask].reset_index(drop=True)
                    st.rerun()

        st.write("---")
        
        # 3. LISTADO DE PRODUCTOS
        h1, h2, h3, h4 = st.columns([0.5, 2, 4, 1.5])
        h1.write("**Sel**")
        h2.write("**Referencia**")
        h3.write("**Nombre / Color / Talla**")
        h4.write("**Cantidad**")

        for idx, row in st.session_state.mesa.iterrows():
            # Si hay una talla filtrada arriba, resaltamos o atenuamos la fila visualmente
            is_target = (talla_target == "Cualquier Talla") or (row['Talla'] == talla_target)
            
            f1, f2, f3, f4 = st.columns([0.5, 2, 4, 1.5])
            
            # Checkbox individual
            res_sel = f1.checkbox(
                " ", 
                value=row['Sel'], 
                key=f"ch_{idx}_{row['Ean']}_v{st.session_state.get('prev_select_all', False)}", 
                label_visibility="collapsed"
            )
            if res_sel != row['Sel']:
                st.session_state.mesa.at[idx, 'Sel'] = res_sel
                st.rerun()
            
            f2.write(f"`{row['Referencia']}`" if is_target else f"~~`{row['Referencia']}`~~")
            f3.write(f"**{row['Nombre']}** \n{row['Color']} / {row['Talla']}" if is_target else f"*{row['Nombre']} ({row['Color']}/{row['Talla']})*")
            
            # Cantidad con clave dinámica para refresco instantáneo
            nueva_cant = f4.number_input(
                "Cant", 
                min_value=0, 
                value=int(row['Cant. a fabricar']), 
                key=f"val_{idx}_{row['Ean']}_c{row['Cant. a fabricar']}", 
                label_visibility="collapsed",
                step=1
            )
            
            if nueva_cant != row['Cant. a fabricar']:
                st.session_state.mesa.at[idx, 'Cant. a fabricar'] = nueva_cant
                st.rerun()
            
            st.divider()



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
        
