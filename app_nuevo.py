import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime
from io import BytesIO
import xlsxwriter
from fpdf import FPDF
import os
import requests

# Webhook directo para Discord (sin .env)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1388850101132460134/FRr5HYdbkxaEsapN5eMvjgcxhlx0H750D2x-vLWHSZ4z5qTMTrheb4las0nSaHVmmJXB"

st.set_page_config(page_title="📊 Estado de Resultados", layout="centered")
st.image("logo.png.png", width=120)
st.title("📊 Estado de Resultados por Cliente")

# 🔐 Mapa de contraseñas por cliente (NIT como contraseña)
CONTRASENAS_CLIENTES = {
    "castro": "84458841",
    "porvenir": "85467683",
    "wilder": "1082943617",
    "maxicarne": "1082892600",
    "fir": "1083010731"
}

# Pantalla de login segura
st.markdown("### 🔐 Acceso privado")
cliente_login = st.selectbox("Selecciona tu empresa", list(CONTRASENAS_CLIENTES.keys()))
password_input = st.text_input("🔑 Ingresa tu contraseña", type="password")

if password_input != CONTRASENAS_CLIENTES[cliente_login]:
    st.warning("⚠️ Ingresa la contraseña correcta para acceder al reporte.")
    st.stop()

if "reporte_cargado" not in st.session_state:
    st.session_state.reporte_cargado = False

conn = sqlite3.connect("dian.db")
clientes = pd.read_sql_query("SELECT DISTINCT cliente FROM facturas WHERE cliente IS NOT NULL", conn)
cliente = cliente_login  # Usamos el cliente autenticado

fechas = pd.read_sql_query("SELECT DISTINCT fecha_emisión FROM facturas WHERE cliente = ?", conn, params=(cliente,))
fechas = pd.to_datetime(fechas["fecha_emisión"], errors="coerce").dropna().sort_values()
fecha_min = fechas.min()
fecha_max = fechas.max()
col1, col2 = st.columns(2)
with col1:
    fecha_inicio = st.date_input("🗕️ Fecha inicial", value=fecha_min, min_value=fecha_min, max_value=fecha_max)
with col2:
    fecha_fin = st.date_input("🗕️ Fecha final", value=fecha_max, min_value=fecha_min, max_value=fecha_max)

if st.button("🔄 Actualizar reporte"):
    st.session_state.reporte_cargado = True
    query = """
        SELECT * FROM facturas 
        WHERE cliente = ? 
        AND DATE(fecha_emisión) BETWEEN ? AND ?
    """
    df = pd.read_sql_query(query, conn, params=(cliente, fecha_inicio, fecha_fin))

    if "sub_total" in df.columns:
        df["sub_total"] = pd.to_numeric(df["sub_total"], errors="coerce").fillna(0)
    else:
        st.error("❌ La columna 'sub_total' no está disponible en los datos filtrados.")
        st.stop()

    if "clasificacion" in df.columns:
        df["clasificacion"] = df["clasificacion"].astype(str).str.strip().str.lower()
    else:
        st.error("❌ La columna 'clasificacion' no está disponible.")
        st.stop()

    clasificaciones_validas = [
        "ingresos", "dev ingreso", "costos", "dev costo",
        "gastos administración", "dev gastos administración",
        "gastos ventas", "dev gastos venta"
    ]
    df = df[df["clasificacion"].isin(clasificaciones_validas)]

    st.session_state.df = df

if st.session_state.reporte_cargado:
    df = st.session_state.df

    def saldo_total(clasif):
        return df[df["clasificacion"] == clasif]["sub_total"].sum()

    ingresos = saldo_total("ingresos")
    dev_ing = saldo_total("dev ingreso")
    costos = saldo_total("costos")
    dev_costos = saldo_total("dev costo")
    gadm = saldo_total("gastos administración")
    dev_gadm = saldo_total("dev gastos administración")
    gventas = saldo_total("gastos ventas")
    dev_gventas = saldo_total("dev gastos venta")

    util_bruta = ingresos - dev_ing - costos + dev_costos
    util_operativa = util_bruta - (gadm - dev_gadm) - (gventas - dev_gventas)

    st.subheader("💾 Estado de Resultados")
    st.metric("Ingresos netos", f"${ingresos - dev_ing:,.2f}")
    st.metric("Costos netos", f"-${costos - dev_costos:,.2f}", delta_color="inverse")
    st.metric("Utilidad Bruta", f"${util_bruta:,.2f}")
    st.metric("Gastos Adm", f"-${gadm - dev_gadm:,.2f}")
    st.metric("Gastos Venta", f"-${gventas - dev_gventas:,.2f}")
    st.metric("Utilidad Operativa", f"${util_operativa:,.2f}")

    with st.expander("🛒 Detalle de compras por proveedor"):
        compras_detalle = df[df["clasificacion"].isin(["costos", "dev costo"])]
        if "nombre_emisor" in compras_detalle.columns:
            resumen_proveedor = compras_detalle.groupby("nombre_emisor")["sub_total"].sum().reset_index()
            resumen_proveedor = resumen_proveedor.rename(columns={"nombre_emisor": "Proveedor"})
            st.dataframe(resumen_proveedor)
        else:
            st.warning("⚠️ La columna 'nombre_emisor' no está disponible en los datos.")

    with st.expander("📦 Detalle de ventas por cliente"):
        ventas_detalle = df[df["clasificacion"].isin(["ingresos", "dev ingreso"])]
        if "nombre_receptor" in ventas_detalle.columns:
            resumen_ventas = ventas_detalle.groupby("nombre_receptor")["sub_total"].sum().reset_index()
            resumen_ventas = resumen_ventas.rename(columns={"nombre_receptor": "Cliente"})
            st.dataframe(resumen_ventas)
        else:
            st.warning("⚠️ La columna 'nombre_receptor' no está disponible en los datos.")

    if st.button("📤 Enviar resumen al canal de Discord"):
        resumen = f"""📊 *Reporte Financiero - {cliente.title()}*
🗓️ Periodo: {fecha_inicio} al {fecha_fin}

✅ Ingresos netos: ${ingresos - dev_ing:,.2f}
📉 Costos netos: -${costos - dev_costos:,.2f}
🧮 Utilidad bruta: ${util_bruta:,.2f}
💼 Gastos Administración: -${gadm - dev_gadm:,.2f}
🛒 Gastos de Venta: -${gventas - dev_gventas:,.2f}
💰 Utilidad operativa: ${util_operativa:,.2f}"""

        if DISCORD_WEBHOOK_URL:
            r = requests.post(DISCORD_WEBHOOK_URL, json={"content": resumen})
            if r.status_code == 204:
                st.success("📨 Enviado correctamente a Discord")
            else:
                st.error(f"❌ Error al enviar a Discord: {r.status_code}")
        else:
            st.error("❌ DISCORD_WEBHOOK_URL no configurado correctamente")

    st.markdown("---")
    st.subheader("⬇️ Descargar reporte en Excel")

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Estado_Resultado", index=False)
        resumen_ventas.to_excel(writer, sheet_name="Ventas", index=False)
        resumen_proveedor.to_excel(writer, sheet_name="Compras", index=False)
        writer.close()
    st.download_button(
        label="📅 Descargar Excel",
        data=buffer.getvalue(),
        file_name=f"estado_resultado_{cliente}_{fecha_inicio}_{fecha_fin}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )




