import streamlit as st
import sqlite3
import pandas as pd
from fpdf import FPDF
import os

# Verificación segura del logo
if os.path.exists("logo.png"):
    st.image("logo.png", width=120)
else:
    st.warning("⚠️ El logo no se encuentra disponible.")

st.title("📊 Portal Estado de Resultados")

# Diccionario de usuarios y contraseñas
USUARIOS = {
    "castro": "1234",
    "porvenir": "5678",
    "maxicarne": "abcd",
    "fir": "efgh",
    "wilder": "9876"
}

def cargar_datos():
    # Mostrar información de depuración para verificar si el archivo existe
    st.info("📁 Buscando archivo: dian.db")
    st.info("📁 Directorio actual: " + os.getcwd())
    st.info("📁 Archivos en el directorio: " + ", ".join(os.listdir()))

    conn = sqlite3.connect("dian.db")
    df = pd.read_sql_query("SELECT * FROM estado_resultados", conn)
    conn.close()
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    df = df.rename(columns={"saldo": "valor"})
    return df

def generar_pdf(cliente, datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, f"Estado de Resultados - Cliente: {cliente}", ln=True, align="C")
    pdf.ln(10)

    clasificados = datos.groupby("clasificacion")["valor"].sum().to_dict()
    ingresos = clasificados.get("ingresos", 0) - clasificados.get("dev_ingreso", 0)
    costos = clasificados.get("costos", 0) - clasificados.get("dev_costo", 0)
    utilidad_bruta = ingresos - costos
    gastos_admin = clasificados.get("gastos_administracion", 0)
    gastos_venta = clasificados.get("gastos_venta", 0)
    utilidad_operativa = utilidad_bruta - gastos_admin - gastos_venta

    pdf.set_font("Arial", "", 12)
    pdf.cell(200, 10, f"Ingresos netos: ${ingresos:,.0f}", ln=True)
    pdf.cell(200, 10, f"Costos netos: ${costos:,.0f}", ln=True)
    pdf.cell(200, 10, f"Utilidad bruta: ${utilidad_bruta:,.0f}", ln=True)
    pdf.cell(200, 10, f"Gastos administración: ${gastos_admin:,.0f}", ln=True)
    pdf.cell(200, 10, f"Gastos de venta: ${gastos_venta:,.0f}", ln=True)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, f"Utilidad operativa: ${utilidad_operativa:,.0f}", ln=True)

    ruta = f"reportes_clientes/estado_resultado_{cliente}.pdf"
    os.makedirs("reportes_clientes", exist_ok=True)
    pdf.output(ruta)
    return ruta

st.subheader("🔐 Iniciar sesión")
cliente = st.text_input("Cliente (nombre/NIT)")
clave = st.text_input("Contraseña", type="password")

if st.button("Ingresar"):
    if cliente in USUARIOS and USUARIOS[cliente] == clave:
        st.success(f"Bienvenido, {cliente.upper()}")
        df = cargar_datos()
        datos_cliente = df[df["cliente"] == cliente]

        if datos_cliente.empty:
            st.warning("No se encontraron datos para este cliente.")
        else:
            st.subheader("📋 Estado de Resultados")
            st.dataframe(datos_cliente)

            clasificados = datos_cliente.groupby("clasificacion")["valor"].sum()
            st.bar_chart(clasificados)

            if st.button("📄 Descargar PDF personalizado"):
                ruta_pdf = generar_pdf(cliente, datos_cliente)
                with open(ruta_pdf, "rb") as file:
                    st.download_button(
                        label="Descargar Estado de Resultados (PDF)",
                        data=file,
                        file_name=os.path.basename(ruta_pdf),
                        mime="application/pdf"
                    )
    else:
        st.error("Acceso denegado ❌")
