import streamlit as st
import pandas as pd
import io
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gextia Factory Pro", layout="wide", page_icon="✂️")

# --- 2. CARGA DE DATOS ---
@st.cache_data
def load_data(file):
    if os.path.exists(file):
        df = pd.read_excel(file, engine='openpyxl')
        df.columns = [str(c).strip().capitalize() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).apply(lambda x: x.replace('.0', '').strip()).replace('nan', '')
        return df
    return None

df_prendas = load_data('prendas.xlsx')
df_comp = load_data('componentes.xlsx')

if 'mesa' not in st.session_state: st.session_state.mesa = pd.DataFrame()
if 'bom' not in st.session_state: st.session_state.bom = pd.DataFrame()

# --- 3. TABS ---
t1, t2, t3, t4 = st.tabs(["🏗️ MESA DE CORTE", "🧬 ASIGNACIÓN", "📋 IMPORT GEXTIA", "📊 LISTA DE COMPRA"])

# --- TAB 1: MESA DE CORTE (PRODUCCIÓN) ---
with t1:
    st.subheader("🏗️ Planificación de Producción")
    if df_prendas is not None:
        c_sel, c_btn = st.columns([3, 1])
        with c_sel: seleccion_refs = st.multiselect("Añadir Referencias:", sorted(df_prendas['Referencia'].unique()))
        with c_btn:
            if st.button("➕ CARGAR", type="primary"):
                nuevos = df_prendas[df_prendas['Referencia'].isin(seleccion_refs)].copy()
                nuevos['Sel'], nuevos['Cant. a fabricar'] = False, 0
                st.session_state.mesa = pd.concat([st.session_state.mesa, nuevos]).drop_duplicates(subset=['Ean'])
                st.rerun()

    if not st.session_state.mesa.empty:
        st.divider()
        c_all, c_talla, c_ops = st.columns([1, 1.5, 3])
        with c_all:
            if st.checkbox("Seleccionar todas", key="master_sel") != st.session_state.get('p_sel', False):
                st.session_state.mesa['Sel'] = st.session_state.master_sel
                st.session_state['p_sel'] = st.session_state.master_sel
                st.rerun()
        with c_talla:
            t_target = st.selectbox("🎯 Filtrar Talla:", ["Todas"] + sorted(st.session_state.mesa['Talla'].unique().tolist()))
        with c_ops:
            mask = st.session_state.mesa['Sel'] == True
            if t_target != "Todas": mask = mask & (st.session_state.mesa['Talla'] == t_target)
            b2, b3, b4 = st.columns(3)
            if b2.button("➕5 Sel."): st.session_state.mesa.loc[mask, 'Cant. a fabricar'] += 5; st.rerun()
            if b3.button("➕10 Sel."): st.session_state.mesa.loc[mask, 'Cant. a fabricar'] += 10; st.rerun()
            if b4.button("🗑️ Quitar Sel."): st.session_state.mesa = st.session_state.mesa[~mask].reset_index(drop=True); st.rerun()

        st.divider()
        for idx, row in st.session_state.mesa.iterrows():
            f1, f2, f3, f4 = st.columns([0.5, 2, 4, 1.5])
            if f1.checkbox(" ", value=row['Sel'], key=f"ch_{idx}_{row['Ean']}_v{st.session_state.get('p_sel', False)}", label_visibility="collapsed") != row['Sel']:
                st.session_state.mesa.at[idx, 'Sel'] = not row['Sel']; st.rerun()
            f2.write(f"`{row['Referencia']}`")
            f3.write(f"**{row['Nombre']}** ({row['Color']} / {row['Talla']})")
            nv = f4.number_input("n", min_value=0, value=int(row['Cant. a fabricar']), key=f"v_{idx}_{row['Ean']}_c{row['Cant. a fabricar']}", label_visibility="collapsed", step=1)
            if nv != row['Cant. a fabricar']: st.session_state.mesa.at[idx, 'Cant. a fabricar'] = nv; st.rerun()
            st.divider()

# --- TAB 2: ASIGNACIÓN (MULTIREFERENCIA) ---
with t2:
    if not st.session_state.mesa.empty:
        st.subheader("🧬 Asignación de Materiales")
        df_comp['Display'] = df_comp.apply(lambda r: f"{r.get('Referencia','')} - {r.get('Nombre','')} | {r.get('Color','')}", axis=1)
        c_m, c_c = st.columns([3, 1])
        with c_m: 
            comp_sel = st.selectbox("Material:", df_comp['Display'].unique())
            row_c = df_comp[df_comp['Display'] == comp_sel].iloc[0]
        with c_c: 
            cons_inj = st.number_input("Consumo Unit.:", min_value=0.0, value=1.0, format="%.3f")
        
        st.write("### 🎯 Definir Destinos")
        f1, f2, f3 = st.columns(3)
        with f1: r_ts = st.multiselect("Filtrar Ref:", sorted(st.session_state.mesa['Referencia'].unique()))
        with f2:
            d_t = st.session_state.mesa if not r_ts else st.session_state.mesa[st.session_state.mesa['Referencia'].isin(r_ts)]
            c_ts = st.multiselect("Filtrar Color:", sorted(d_t['Color'].unique()))
        with f3:
            d_t2 = d_t if not c_ts else d_t[d_t['Color'].isin(c_ts)]
            t_ts = st.multiselect("Filtrar Talla:", sorted(d_t2['Talla'].unique()))
            
        final_df = d_t2 if not t_ts else d_t2[d_t2['Talla'].isin(t_ts)]
        st.info(f"Se inyectará en **{len(final_df)}** variantes.")
        
        if st.button("✂️ EJECUTAR INYECCIÓN Y CORTE", type="primary", use_container_width=True):
            nuevas = pd.DataFrame({
                'Nombre de producto': final_df['Nombre'], 'Cod Barras Variante': final_df['Ean'],
                'Ref Prenda': final_df['Referencia'], 'Col Prenda': final_df['Color'], 'Tal Prenda': final_df['Talla'],
                'Cantidad producto final': final_df['Cant. a fabricar'], 'Ref Comp': row_c.get('Referencia',''),
                'Nom Comp': row_c.get('Nombre',''), 'Col Comp': row_c.get('Color',''), 'EAN Componente': row_c.get('Ean',''),
                'Cantidad': cons_inj, 'Ud': row_c.get('Unidad de medida','Un'), 'Tipo de lista de material': 'Fabricación', 'Subcontratista': ''
            })
            st.session_state.bom = pd.concat([st.session_state.bom, nuevas]).drop_duplicates()
            st.success("✂️ ¡Material cortado y asignado!"); st.balloons()
    else: st.warning("Mesa vacía.")

# --- TAB 3: ESCANDALLO (IMPORTACIÓN GEXTIA) ---
with t3:
    if not st.session_state.bom.empty:
        st.subheader("📋 Fichero de Importación de Escandallos")
        st.write("Edita directamente si necesitas un ajuste final antes de exportar.")
        df_edit = st.data_editor(st.session_state.bom, use_container_width=True, hide_index=True)
        st.session_state.bom = df_edit

        # Formato GEXTIA
        cols_gextia = ['Nombre de producto', 'Cod Barras Variante', 'Cantidad producto final', 
                       'Tipo de lista de material', 'Subcontratista', 'EAN Componente', 'Cantidad', 'Ud']
        df_gextia = df_edit[cols_gextia].copy()
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_gextia.to_excel(writer, index=False, sheet_name='Lista de Materiales')
        
        st.divider()
        st.download_button(
            label="📥 DESCARGAR EXCEL PARA GEXTIA",
            data=output.getvalue(),
            file_name=f"Gextia_BOM_{datetime.now().strftime('%d%m_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- TAB 4: LISTA DE LA COMPRA ---
with t4:
    if not st.session_state.bom.empty:
        st.subheader("📊 Consolidado de Necesidades de Compra")
        
        # Sincronizamos con las cantidades actuales de la mesa
        df_calc = st.session_state.bom.copy()
        df_cantidades = st.session_state.mesa[['Ean', 'Cant. a fabricar']]
        df_calc = df_calc.drop(columns=['Cantidad producto final']).merge(df_cantidades, left_on='Cod Barras Variante', right_on='Ean', how='left')
        
        df_calc['Total Compra'] = df_calc['Cantidad'].astype(float) * df_calc['Cant. a fabricar'].astype(float)
        
        # Agrupamos por Componente
        compra_final = df_calc.groupby(['Ref Comp', 'Nom Comp', 'Col Comp', 'Ud'])['Total Compra'].sum().reset_index()
        compra_final = compra_final[compra_final['Total Compra'] > 0] # Solo lo que tiene cantidad
        
        st.dataframe(compra_final, use_container_width=True, hide_index=True)
        
        output_compra = io.BytesIO()
        with pd.ExcelWriter(output_compra, engine='openpyxl') as writer:
            compra_final.to_excel(writer, index=False, sheet_name='Lista de Compra')
            
        st.download_button(
            label="📥 DESCARGAR LISTA DE LA COMPRA",
            data=output_compra.getvalue(),
            file_name=f"Lista_Compra_{datetime.now().strftime('%d%m_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
