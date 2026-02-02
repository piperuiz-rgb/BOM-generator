import streamlit as st
import pandas as pd
import io
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gextia Factory Pro", layout="wide", page_icon="✂️")

# --- 2. MOTOR DE DATOS ---
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

# --- 4. TABS ---
t1, t2, t3, t4 = st.tabs(["🏗️ MESA DE CORTE", "🧬 ASIGNACIÓN", "📋 ESCANDALLO", "📊 COMPRAS"])

# --- TAB 1: MESA ---
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
            t_target = st.selectbox("🎯 Talla:", ["Todas"] + sorted(st.session_state.mesa['Talla'].unique().tolist()))
        with c_ops:
            mask = st.session_state.mesa['Sel'] == True
            if t_target != "Todas": mask = mask & (st.session_state.mesa['Talla'] == t_target)
            b2, b3, b4 = st.columns(3)
            if b2.button("➕5"): st.session_state.mesa.loc[mask, 'Cant. a fabricar'] += 5; st.rerun()
            if b3.button("➕10"): st.session_state.mesa.loc[mask, 'Cant. a fabricar'] += 10; st.rerun()
            if b4.button("🗑️ Quitar"): st.session_state.mesa = st.session_state.mesa[~mask].reset_index(drop=True); st.rerun()

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

# --- TAB 2: ASIGNACIÓN (MULTIREFERENCIA Y FILTROS COMBINADOS) ---
with t2:
    if not st.session_state.mesa.empty:
        st.subheader("🧬 Asignación de Materiales Masiva")
        
        # 1. SELECCIÓN DEL COMPONENTE
        df_comp['Display'] = df_comp.apply(lambda r: f"{r.get('Referencia','')} - {r.get('Nombre','')} | {r.get('Color','')}", axis=1)
        
        c_m, c_c = st.columns([3, 1])
        with c_m: 
            comp_sel = st.selectbox("Material a añadir:", df_comp['Display'].unique())
            row_c = df_comp[df_comp['Display'] == comp_sel].iloc[0]
        with c_c: 
            cons_inj = st.number_input("Consumo Unitario:", min_value=0.0, value=1.0, format="%.3f", step=0.001)
        
        st.divider()
        
        # 2. DESTINOS CON MULTISELECCIÓN
        st.write("### 🎯 Definir Destinos")
        f1, f2, f3 = st.columns(3)
        
        with f1:
            # Ahora es un multiselect para permitir varias referencias a la vez
            opciones_refs = sorted(st.session_state.mesa['Referencia'].unique().tolist())
            refs_targets = st.multiselect("Filtrar por Referencia(s):", opciones_refs, help="Si dejas vacío, se aplica a TODAS")
            
        with f2:
            # Filtramos colores basados en las referencias seleccionadas
            if refs_targets:
                df_temp = st.session_state.mesa[st.session_state.mesa['Referencia'].isin(refs_targets)]
            else:
                df_temp = st.session_state.mesa
                
            opciones_colores = sorted(df_temp['Color'].unique().tolist())
            cols_targets = st.multiselect("Filtrar por Color(es):", opciones_colores, help="Si dejas vacío, se aplica a TODOS los colores")
            
        with f3:
            # Filtramos tallas basados en referencias y colores seleccionados
            df_temp2 = df_temp
            if cols_targets:
                df_temp2 = df_temp2[df_temp2['Color'].isin(cols_targets)]
            
            opciones_tallas = sorted(df_temp2['Talla'].unique().tolist())
            tals_targets = st.multiselect("Filtrar por Talla(s):", opciones_tallas, help="Si dejas vacío, se aplica a TODAS las tallas")

        # 3. FILTRADO FINAL Y VISTA PREVIA
        final_df = df_temp2
        if tals_targets:
            final_df = final_df[final_df['Talla'].isin(tals_targets)]
            
        st.info(f"✨ El material se inyectará en **{len(final_df)}** variantes seleccionadas.")
        
        # 4. BOTÓN DE EJECUCIÓN CON TIJERAS
        if st.button("✂️ EJECUTAR INYECCIÓN Y CORTE", type="primary", use_container_width=True):
            if final_df.empty:
                st.error("No hay variantes que coincidan con la combinación de filtros.")
            else:
                nuevas = pd.DataFrame({
                    'Nombre de producto': final_df['Nombre'],
                    'Cod Barras Variante': final_df['Ean'],
                    'Ref Prenda': final_df['Referencia'],
                    'Col Prenda': final_df['Color'],
                    'Tal Prenda': final_df['Talla'],
                    'Cantidad producto final': final_df['Cant. a fabricar'],
                    'Ref Comp': row_c.get('Referencia',''),
                    'Nom Comp': row_c.get('Nombre',''),
                    'Col Comp': row_c.get('Color',''),
                    'EAN Componente': row_c.get('Ean',''),
                    'Cantidad': cons_inj,
                    'Ud': row_c.get('Unidad de medida','Un'),
                    'Tipo de lista de material': 'Fabricación',
                    'Subcontratista': ''
                })
                
                st.session_state.bom = pd.concat([st.session_state.bom, nuevas]).drop_duplicates()
                st.success("✂️ ¡Corte y asignación completados con éxito!")
                st.balloons()

# --- TABS 3 Y 4 (Igual que antes pero integradas) ---
with t3:
    if not st.session_state.bom.empty:
        df_e = st.data_editor(st.session_state.bom, use_container_width=True, hide_index=True)
        st.session_state.bom = df_e
with t4:
    if not st.session_state.bom.empty:
        df_c = st.session_state.bom.copy()
        df_m_l = st.session_state.mesa[['Ean', 'Cant. a fabricar']]
        df_c = df_c.drop(columns=['Cantidad producto final']).merge(df_m_l, left_on='Cod Barras Variante', right_on='Ean', how='left')
        df_c['Total'] = df_c['Cantidad'] * df_c['Cant. a fabricar']
        res = df_c.groupby(['Ref Comp', 'Nom Comp', 'Col Comp', 'Ud'])['Total'].sum().reset_index()
        st.dataframe(res, use_container_width=True, hide_index=True)
        
