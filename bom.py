import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gextia BOM Ultra-Fast", layout="wide")

# --- CARGA DE DATOS CORREGIDA ELEMENTO A ELEMENTO ---
@st.cache_data
def load_excel(file):
    if os.path.exists(file):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            df.columns = [str(c).strip() for c in df.columns]
            
            columnas_criticas = ['EAN', 'Referencia', 'Nombre', 'Color', 'Talla']
            for col in columnas_criticas:
                if col in df.columns:
                    # Limpieza profunda de strings para evitar errores de tipo 'Series'
                    df[col] = df[col].astype(str).apply(lambda x: x.replace('.0', '').strip())
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

# --- BARRA LATERAL: RESPALDO EN EXCEL (MÁS SEGURO) ---
with st.sidebar:
    st.header("💾 Copia de Seguridad")
    
    # 1. BOTÓN PARA GUARDAR
    st.subheader("Guardar Trabajo")
    if not st.session_state.bom_final.empty:
        output_backup = io.BytesIO()
        with pd.ExcelWriter(output_backup, engine='openpyxl') as writer:
            st.session_state.bom_final.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Respaldo (.xlsx)",
            data=output_backup.getvalue(),
            file_name=f"respaldo_BOM_{datetime.now().strftime('%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        st.info("💡 Guarda este archivo para no perder el progreso.")
    else:
        st.warning("⚠️ Inyecta materiales para poder guardar.")
    
    st.divider()
    
    # 2. BOTÓN PARA RECUPERAR
    st.subheader("Recuperar Trabajo")
    archivo_recuperacion = st.file_uploader("Sube tu respaldo (.xlsx)", type=['xlsx'])
    
    if archivo_recuperacion:
        if st.button("🔄 Restaurar Sesión Ahora", use_container_width=True):
            try:
                # Cargamos el Excel de respaldo
                df_recuperado = pd.read_excel(archivo_recuperacion, engine='openpyxl')
                
                # Aseguramos limpieza de datos como en la carga inicial
                for col in df_recuperado.columns:
                    df_recuperado[col] = df_recuperado[col].astype(str).apply(lambda x: x.replace('.0', '').strip())
                    df_recuperado[col] = df_recuperado[col].replace('nan', '')
                
                # Convertir la columna Cantidad a número para que el editor funcione
                if 'Cantidad' in df_recuperado.columns:
                    df_recuperado['Cantidad'] = pd.to_numeric(df_recuperado['Cantidad'], errors='coerce')
                
                st.session_state.bom_final = df_recuperado
                st.success("✅ ¡Trabajo restaurado con éxito!")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo importar: {e}")


# --- CUERPO PRINCIPAL ---
st.title("👗 Gextia BOM: Gestión Profesional")

# Funciones de formato visual
def fmt_prenda(row): return f"{row['Referencia']} - {row['Nombre']} ({row['Color']} / {row['Talla']})"
def fmt_comp(row): return f"{row['Referencia']} - {row['Nombre']} | {row['Color']} | T: {row.get('Talla', 'U')}"

tab1, tab2, tab3 = st.tabs(["🏗️ MESA DE TRABAJO", "🧬 ASIGNACIÓN", "📋 REVISIÓN Y EXPORTACIÓN"])

# --- PESTAÑA 1: SELECCIÓN ---
with tab1:
    if df_prendas is not None:
        st.subheader("Seleccionar Productos para el Escandallo")
        opciones_refs = sorted(df_prendas['Referencia'].unique())
        refs_sel = st.multiselect("Filtrar por Referencia Base:", opciones_refs)
        
        if st.button("Añadir a Mesa de Trabajo", type="primary"):
            nuevos = df_prendas[df_prendas['Referencia'].isin(refs_sel)]
            st.session_state.mesa_trabajo = pd.concat([st.session_state.mesa_trabajo, nuevos]).drop_duplicates()
            st.rerun()

        if not st.session_state.mesa_trabajo.empty:
            st.write(f"📍 Variantes en mesa: **{len(st.session_state.mesa_trabajo)}**")
            st.dataframe(st.session_state.mesa_trabajo[['Referencia', 'Nombre', 'Color', 'Talla', 'EAN']], use_container_width=True, hide_index=True)
            if st.button("Vaciar Mesa"):
                st.session_state.mesa_trabajo = pd.DataFrame()
                st.rerun()

# --- PESTAÑA 2: ASIGNACIÓN MASIVA ---
with tab2:
    if st.session_state.mesa_trabajo.empty or df_comp is None:
        st.info("Añade productos en la pestaña 1.")
    else:
        st.subheader("1. Selección del Material")
        df_comp['Display'] = df_comp.apply(fmt_comp, axis=1)
        comp_sel_display = st.selectbox("Buscar Material:", df_comp['Display'].unique())
        row_comp = df_comp[df_comp['Display'] == comp_sel_display].iloc[0]
        
        st.divider()
        st.subheader("2. Destinos")
        refs_en_mesa = sorted(st.session_state.mesa_trabajo['Referencia'].unique())
        destinos_refs = st.multiselect("Aplicar a estas prendas:", refs_en_mesa, default=refs_en_mesa)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            modo = st.radio("Filtrar por:", ["Todas", "Colores específicos", "Tallas específicas"])
        with c2:
            filtros = []
            if modo == "Colores específicos":
                filtros = st.multiselect("Colores:", sorted(st.session_state.mesa_trabajo['Color'].unique()))
            elif modo == "Tallas específicas":
                filtros = st.multiselect("Tallas:", sorted(st.session_state.mesa_trabajo['Talla'].unique()))
        with c3:
            consumo = st.number_input("Consumo:", min_value=0.0, value=1.0, format="%.3f")
            ud = row_comp['Unidad de medida']

        if st.button("🚀 Inyectar Material", type="primary"):
            target = st.session_state.mesa_trabajo[st.session_state.mesa_trabajo['Referencia'].isin(destinos_refs)].copy()
            if modo == "Colores específicos" and filtros: target = target[target['Color'].isin(filtros)]
            elif modo == "Tallas específicas" and filtros: target = target[target['Talla'].isin(filtros)]
            
            nuevas = pd.DataFrame({
                'Nombre de producto': target['Nombre'], 'Ref Prenda': target['Referencia'],
                'Col Prenda': target['Color'], 'Tal Prenda': target['Talla'],
                'Cod Barras Variante': target['EAN'], 'Cantidad producto final': 1,
                'Tipo de lista de material': 'Fabricación', 'Subcontratista': '',
                'Ref Comp': row_comp['Referencia'], 'Nom Comp': row_comp['Nombre'],
                'Col Comp': row_comp['Color'], 'Tal Comp': row_comp.get('Talla', 'U'),
                'EAN Componente': row_comp['EAN'], 'Cantidad': consumo, 'Ud': ud
            })
            st.session_state.bom_final = pd.concat([st.session_state.bom_final, nuevas]).drop_duplicates()
            st.success("Asignación completada.")

# --- PESTAÑA 3: REVISIÓN Y EXPORTACIÓN ---
with tab3:
    if not st.session_state.bom_final.empty:
        st.subheader("Validación Final")
        df_view = st.session_state.bom_final.sort_values(by=['Ref Prenda', 'Col Prenda', 'Tal Prenda'])
        
        # EDITOR DE TABLA
        df_editado = st.data_editor(
            df_view,
            column_config={
                "Cantidad": st.column_config.NumberColumn("Consumo", format="%.3f"),
                "Nombre de producto": st.column_config.Column(disabled=True),
                "Ref Prenda": st.column_config.Column(disabled=True),
                "Col Prenda": st.column_config.Column(disabled=True),
                "Tal Prenda": st.column_config.Column(disabled=True),
                "Nom Comp": st.column_config.Column("Material", disabled=True)
            },
            hide_index=True, use_container_width=True, num_rows="dynamic"
        )
        st.session_state.bom_final = df_editado

        # EXPORTACIÓN LIMPIA PARA GEXTIA
        columnas_gextia = ['Nombre de producto', 'Cod Barras Variante', 'Cantidad producto final', 
                           'Tipo de lista de material', 'Subcontratista', 'EAN Componente', 'Cantidad', 'Ud']
        
        st.divider()
        c_ex1, c_ex2 = st.columns(2)
        with c_ex1:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_editado[columnas_gextia].to_excel(writer, index=False)
            st.download_button("📥 DESCARGAR EXCEL GEXTIA", output.getvalue(), "import_gextia.xlsx", use_container_width=True)
        with c_ex2:
            if st.button("⚠️ BORRAR TODO"):
                st.session_state.bom_final = pd.DataFrame()
                st.rerun()
                
