import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# Configuración inicial de la página
st.set_page_config(page_title="CRM Seguimiento de Cobros", layout="wide", page_icon="💶")

# --- SISTEMA DE LOGIN ---
def check_password():
    if "login_ok" not in st.session_state:
        st.session_state["login_ok"] = False

    if not st.session_state["login_ok"]:
        st.markdown("### 🔐 Acceso al Sistema de Cobros")
        usu = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        
        if st.button("Entrar"):
            # Para 1 usuario, leemos de los secrets de Streamlit (o valores por defecto para pruebas)
            try:
                valid_user = st.secrets["admin_user"]["username"]
                valid_pwd = st.secrets["admin_user"]["password"]
            except:
                valid_user = "admin"
                valid_pwd = "admin" # Cambia esto más adelante
                
            if usu == valid_user and pwd == valid_pwd:
                st.session_state["login_ok"] = True
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
        return False
    return True

# Si el login no es correcto, detenemos la ejecución de la app aquí
if not check_password():
    st.stop()

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        # 1. Intenta leer credenciales de Streamlit Cloud (Producción)
        creds_dict = dict(st.secrets["gcp_credentials"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    except Exception:
        # 2. Si falla, busca el archivo local (Desarrollo)
        try:
            df_facturas, df_seguimientos, ws_facturas, ws_seguimientos = get_data()
        except Exception as e:
            st.error("Error al conectar con la hoja de datos.")
            st.warning(f"Detalle técnico exacto del error: {e}")
            st.stop()
    
    return gspread.authorize(creds)

gc = init_connection()

# 🔴 ¡IMPORTANTE! Reemplaza esto con el ID de tu Google Sheet (lo sacas de la URL del navegador)
SHEET_ID = "1co06HSyK0o0RjnVg5HE9UgnuB2l47OKY3itcdkCsvPM"

@st.cache_data(ttl=60) # Refresca los datos cada 60 segundos
def get_data():
    sh = gc.open_by_key(SHEET_ID)
    ws_facturas = sh.worksheet("Facturas")
    ws_seguimientos = sh.worksheet("Seguimientos")
    
    df_fac = pd.DataFrame(ws_facturas.get_all_records())
    df_seg = pd.DataFrame(ws_seguimientos.get_all_records())
    
    # Asegurar que las columnas sean string para facilitar búsquedas
    if not df_fac.empty:
        df_fac['Numero_Factura'] = df_fac['Numero_Factura'].astype(str)
    if not df_seg.empty:
        df_seg['Numero_Factura'] = df_seg['Numero_Factura'].astype(str)
        
    return df_fac, df_seg, ws_facturas, ws_seguimientos

# --- INTERFAZ DE USUARIO ---
st.title("💶 CRM: Seguimiento de Facturas")

try:
    df_facturas, df_seguimientos, ws_facturas, ws_seguimientos = get_data()
except Exception as e:
    st.error(f"Error al conectar con la hoja de datos: Verifica que el SHEET_ID sea correcto y la Service Account tenga permisos de Editor.")
    st.stop()

# Creación de pestañas
tab1, tab2 = st.tabs(["🗂️ Gestión y Registro", "📈 Dashboard Analítico"])

with tab1:
    st.subheader("Buscador de Facturas")
    
    col1, col2, col3 = st.columns(3)
    b_cliente = col1.text_input("🔍 Buscar por Nombre/Código Cliente")
    b_factura = col2.text_input("🧾 Buscar por Nº Factura")
    
    # Filtrar datos
    if not df_facturas.empty:
        df_filtrado = df_facturas.copy()
        if b_cliente:
            df_filtrado = df_filtrado[df_filtrado['Nombre_Cliente'].str.contains(b_cliente, case=False, na=False) | 
                                      df_filtrado['Codigo_Cliente'].astype(str).str.contains(b_cliente, case=False, na=False)]
        if b_factura:
            df_filtrado = df_filtrado[df_filtrado['Numero_Factura'].str.contains(b_factura, case=False, na=False)]
            
        st.dataframe(df_filtrado, use_container_width=True)
        
        # --- SECCIÓN DE AÑADIR SEGUIMIENTO ---
        st.divider()
        st.subheader("Añadir Nuevo Seguimiento")
        
        facturas_lista = df_filtrado['Numero_Factura'].tolist() if not df_filtrado.empty else []
        
        with st.form("form_seguimiento"):
            c1, c2 = st.columns(2)
            sel_factura = c1.selectbox("Selecciona la Factura", facturas_lista)
            fecha_cont = c2.date_input("Fecha de Contacto", datetime.today())
            
            c3, c4 = st.columns(2)
            tipo_cont = c3.selectbox("Canal de Contacto", ["Teléfono", "Email", "WhatsApp", "Presencial"])
            info_asesor = c4.radio("¿Se informó al asesor?", ["Sí", "No"], horizontal=True)
            
            notas = st.text_area("Notas / Comentarios del cliente")
            
            submit_btn = st.form_submit_button("Guardar Seguimiento")
            
            if submit_btn and sel_factura:
                nuevo_registro = [sel_factura, str(fecha_cont), tipo_cont, info_asesor, notas]
                ws_seguimientos.append_row(nuevo_registro)
                st.success("✅ Seguimiento guardado correctamente.")
                st.cache_data.clear() # Limpia caché para recargar
                st.rerun()
                
        # --- VER HISTORIAL DE SEGUIMIENTOS ---
        if sel_factura and not df_seguimientos.empty:
            st.markdown(f"**Historial de la factura {sel_factura}:**")
            historial = df_seguimientos[df_seguimientos['Numero_Factura'] == sel_factura]
            st.dataframe(historial, use_container_width=True)

    else:
        st.info("No hay facturas registradas. Añade datos directamente en el Google Sheet para empezar.")

with tab2:
    st.subheader("Panel de Control")
    if not df_facturas.empty:
        colA, colB, colC = st.columns(3)
        
        # Transformar importe a numérico por si hay errores de formato
        df_facturas['Importe_Num'] = pd.to_numeric(df_facturas['Importe'], errors='coerce').fillna(0)
        
        total_deuda = df_facturas[df_facturas['Estado'].str.lower() != 'cobrado']['Importe_Num'].sum()
        total_facturas = len(df_facturas)
        pendientes = len(df_facturas[df_facturas['Estado'].str.lower() != 'cobrado'])
        
        colA.metric("Deuda Pendiente Total", f"{total_deuda:,.2f} €")
        colB.metric("Facturas Totales", total_facturas)
        colC.metric("Facturas Pendientes", pendientes)
        
        st.divider()
        st.markdown("**Estado de las Facturas**")
        estado_counts = df_facturas['Estado'].value_counts()
        st.bar_chart(estado_counts)
    else:
        st.info("Sin datos suficientes para mostrar métricas.")
