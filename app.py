import streamlit as st
from datetime import datetime
from pandas import to_datetime
from logic import calculate_ot_premium, apply_phaseout
from pdf_utils import extract_amounts
from pdf_export import generate_pdf

# -------------------------
# PAYWALL GATE (HARD BLOCK)
# -------------------------
if "paid" not in st.session_state:
    st.session_state.paid = False

# Check URL query param on load/redirect
query_params = st.query_params

# ─── DEBUG LINES ───
st.write("DEBUG: Raw query params:", query_params)
st.write("DEBUG: Paid state before check:", st.session_state.paid)
st.write("DEBUG: Is 'paid' in params?", "paid" in query_params)

if st.session_state.paid:
    # Clean URL after setting state (hides ?paid=true)
    st.query_params.pop("paid", None)
    
# Extra safety: if params exist but state not set → set and rerun immediately
if "paid" in query_params and not st.session_state.paid:
    st.session_state.paid = True
    st.rerun()  # This forces a fresh run where state is now True
    
# If not paid via state or param → show paywall
if not st.session_state.paid:
    st.title("🔒 OBBB 2025 Calculator")
    st.write("""
    This tool is available after a one-time payment.
    
    - Full calculator access
    - PDF report download
    - Updated for the One Big Beatiful Bill (OBBB) 2025 rules
    """)

    st.markdown("### 💳 One-time access: **$1.00**")

    st.link_button(
        "Unlock Access",
        st.secrets["stripe"]["pay_link"]
    )

    st.stop()  # 🚨 NOTHING BELOW RUNS

# -------------------------
# PAGE CONFIG
# -------------------------
st.set_page_config(
    page_title="OBBB 2025 Calculator",
    layout="centered"
)

# Textos in spanish and english
texts = {
    "es": {
        "title": "Calculadora de Deducciones OBBB",
        "desc": "Esta herramienta gratuita te ayuda a estimar deducciones por propinas y horas extras según la Ley OBBB 2025.\nIMPORTANTE: Esto NO es asesoría fiscal oficial. Consulta a un contador o al IRS.",
        "info_upload": "Sube uno o varios PDFs (W-2, 1099, paystubs, talones de pago) para extraer y sumar datos automaticamente. Ideal para parejas casadas (suma de ambos). Maximo 5 archivos.",
        "disclaimer_extract": "ATENCION: Siempre verifica y edita los datos extraidos automaticamente del PDF. La lectura puede tener errores (ej. numeros mal reconocidos).",
        "filing_status_label": "Estado civil para impuestos",
        "filing_options": ["Soltero / Cabeza de familia", "Casado declarando conjuntamente"],
        "magi_label": "MAGI estimado ($)",
        "magi_help": "MAGI significa 'Modified Adjusted Gross Income' (Ingreso Bruto Ajustado Modificado).\nEs el numero que usa el IRS para decidir si tus deducciones se reducen o eliminan.\nDonde encontrarlo o estimarlo:\n- En tu W-2: Casilla 1 (Wages, tips, other compensation) como base.\n- En paystubs: suma 'YTD Gross' o 'Total Earnings' del año.\n- Si no tienes la declaracion final: suma todos tus ingresos del año (salario, propinas, OT, intereses, etc.) menos deducciones basicas.\nUsa una estimacion anual realista.",
        "tips_label": "Monto total de propinas calificadas ($)",
        "tips_help": "Suma TODAS las propinas que recibiste y reportaste durante TODO el año.\nDonde encontrarlo:\n- W-2 Casilla 7 (Social security tips) o Casilla 8 (Allocated tips)\n- 1099 o registros diarios si trabajas por cuenta propia\nSolo cuenta propinas que califican (de ocupaciones habituales con propinas: meseros, bartenders, etc.).",
        "ot_label": "Pago total recibido por horas extras ($)",
        "ot_help": "Suma TODO el dinero que te pagaron por concepto de horas extras durante TODO el año.\nDonde encontrarlo:\n- En cada paystub busca 'Over-Time', 'Overtime', 'OT Pay' o 'Premium OT'\n- Suma TODOS los montos de overtime de todos tus talones del año\nImportante: incluye tanto la base regular como la prima extra (ej. en tiempo y medio incluye los $10 regulares + $5 de prima).",
        "multiplier_label": "Multiplicador de horas extras",
        "multiplier_help": "Es el factor por el que se multiplica tu tarifa normal en horas extras.\nEjemplos comunes:\n- 1.5 = tiempo y medio (lo más frecuente, paga 1.5 veces la tarifa regular)\n- 2.0 = doble tiempo (paga 2 veces la tarifa regular)\nBusca en tu paystub 'Over-Time Rate' o 'OT Rate', o compara tu pago regular vs. pago por hora extra (ej. si regular es /$20 y OT es /$30, es 1.5). No confundas con el pago total de OT (incluye base + prima).",
        "upload_label": "1️⃣ Sube tus documentos de Impuestos",
        "upload_instructions": "Ejemplo PDF(s) (W-2, 1099, paystub) - max 5 archivos",
        "calc_button": "Calcular deducciones estimadas",
        "results_title": "📊 Resultados",
        "tips_ded": "Deducción por propinas",
        "ot_ded": "Deducción por prima de horas extras",
        "total_ded": "💰 Total Deducción Aproximada: $",
        "summary": "Resumen",
        "footer": "Hecho por Carlos E. Martinez",
        "uploaded_file_info": "Valores extraidos (revise con cuidado):",
        "uploaded_file_info_field": "Descripción",
        "uploaded_file_info_value": "Valor",
        "uploaded_file_results_confirmation": "Confirmo que estos valores son correctos",
        "income_label": "2️⃣ Información de Ingresos",
    },
    "en": {
        "title": "OBBB Deductions Calculator",
        "desc": "This free tool helps estimate deductions for qualified tips and overtime under the OBBB Act 2025.\nIMPORTANT: This is NOT official tax advice. Consult a tax professional or the IRS.",
        "info_upload": "Upload one or multiple PDFs (W-2, 1099, paystubs, check stubs) to auto-extract and sum data. Great for married couples (combine both). Max 5 files.",
        "disclaimer_extract": "WARNING: Always verify and edit auto-extracted data from PDF. Reading errors may occur (e.g., misread numbers).",
        "filing_status_label": "Filing Status",
        "filing_options": ["Single / Head of Household", "Married Filing Jointly"],
        "magi_label": "Estimated MAGI ($)",
        "magi_help": "MAGI stands for 'Modified Adjusted Gross Income'.\nIt's the number the IRS uses to determine if your deductions are reduced or eliminated.\nWhere to find or estimate it:\n- On your W-2: Box 1 (Wages, tips, other compensation) as base.\n- On paystubs: sum 'YTD Gross' or 'Total Earnings' for the year.\n- If no final tax return: add up all your income for the year (wages, tips, OT, interest, etc.) minus basic deductions.\nUse a realistic annual estimate.",
        "tips_label": "Total Qualified Tips ($)",
        "tips_help": "Sum ALL qualified tips you received and reported during the entire year.\nWhere to find it:\n- W-2 Box 7 (Social security tips) or Box 8 (Allocated tips)\n- 1099 or daily tip logs if self-employed\nOnly include tips from customary tipped occupations (servers, bartenders, etc.).",
        "ot_label": "Total Overtime Pay ($)",
        "ot_help": "Sum ALL the money you were paid for overtime work during the entire year.\nWhere to find it:\n- On each paystub look for 'Over-Time', 'Overtime', 'OT Pay' or 'Premium OT'\n- Add up ALL overtime amounts from every paystub of the year\nImportant: includes both the regular base pay for those hours + the premium (extra half or double).",
        "multiplier_label": "Overtime Multiplier",
        "multiplier_help": "This is the factor by which your regular rate is multiplied for overtime hours.\nCommon examples:\n- 1.5 = time and a half (most common, pays 1.5 times regular rate)\n- 2.0 = double time (pays 2 times regular rate)\nWhere to find it:\n- On your paystub: look for 'Over-Time Rate' or 'OT Rate'\n- Or compare: if your regular rate is $20 and overtime rate is $30 → it's 1.5\nDo NOT confuse with total overtime pay (that already includes base + premium).",
        "upload_label": "1️⃣ Upload Tax Documents",
        "upload_instructions": "Example PDF(s) (W-2, 1099, paystub) - max 5 files",
        "calc_button": "Calculate Estimated Deductions",
        "results_title": "📊 Results",
        "tips_ded": "Tips Deduction",
        "ot_ded": "Overtime Premium Deduction",
        "total_ded": "💰 Total Estimated Deduction: $",
        "summary": "Summary",
        "footer": "Made by Carlos E. Martinez",
        "uploaded_file_info": "Extracted values (review carefully):",
        "uploaded_file_info_field": "Field",
        "uploaded_file_info_value": "Value",
        "uploaded_file_results_confirmation": "I confirm these values are correct",
        "income_label": "2️⃣ Income Information",
    }
}

# Language selector
language = st.selectbox("Idioma / Language", ["Español", "English"], index=0)
lang = "es" if language == "Español" else "en"

# Load text dictionary
t = texts[lang]

st.title(t["title"])

st.info(t["desc"])

# -------------------------
# UPLOAD SECTION
# -------------------------
st.markdown("---")
st.subheader(t["upload_label"])

uploaded_files = st.file_uploader(
    t["upload_instructions"],
    type="pdf",
    accept_multiple_files=True
)

extracted_magi = extracted_tips = extracted_ot = 0.0
confirmed = False

if uploaded_files:
    extracted_magi, extracted_tips, extracted_ot = extract_amounts(uploaded_files)

    st.info(t["uploaded_file_info"])
    st.table({
        t["uploaded_file_info_field"]: [t["magi_label"], t["tips_label"], t["ot_label"]],
        t["uploaded_file_info_value"]: [
            f"{extracted_magi:,.0f}",
            f"{extracted_tips:,.0f}",
            f"{extracted_ot:,.0f}"
        ]
    })

    confirmed = st.checkbox(t["uploaded_file_results_confirmation"])

# -------------------------
# INPUT SECTION
# -------------------------
st.markdown("---")
st.subheader(t["income_label"])

col1, col2 = st.columns(2)

with col1:
    magi = st.number_input(
        t["magi_label"], 
        min_value=0.0, 
        value=extracted_magi if confirmed else 0.0, 
        step=1000.0,
        help=t["magi_help"]
    )

with col2:
    filing_status = st.selectbox(
        t["filing_status_label"],
        t["filing_options"]
    )

tips_amount = st.number_input(
    t["tips_label"],
    min_value=0.0,
    value=extracted_tips if confirmed else 0.0,
    step=100.0,
    help=t["tips_help"]
)

ot_total = st.number_input(
    t["ot_label"],
    min_value=0.0,
    value=extracted_ot if confirmed else 0.0,
    step=100.0,
    help=t["ot_help"]
)

ot_multiplier = st.number_input(
    t["multiplier_label"],
    min_value=1.0,
    value=1.5,
    step=0.5, 
    help=t["multiplier_help"]
)

# -------------------------
# CALCULATION
# -------------------------
st.markdown("---")

if st.button(t["calc_button"], type="primary"):
    ot_premium = calculate_ot_premium(ot_total, ot_multiplier)

    if filing_status == t["filing_options"][1]:
        max_tips = 25000
        max_ot = 25000
        phase_start = 300000
    else:
        max_tips = 25000
        max_ot = 12500
        phase_start = 150000

    tips_ded = min(
        tips_amount,
        apply_phaseout(magi, max_tips, phase_start)
    )

    ot_ded = min(
        ot_premium,
        apply_phaseout(magi, max_ot, phase_start)
    )

    total = tips_ded + ot_ded

    st.subheader(t["results_title"])
    st.success(f"{t['total_ded']} {total:,.0f}")

    st.metric(t["tips_ded"], f"${tips_ded:,.0f}")
    st.metric(t["ot_ded"], f"${ot_ded:,.0f}")

    pdf_bytes = generate_pdf(
    total,
    tips_ded,
    ot_ded
)

    st.download_button(
        label="📄 Download PDF report",
        data=pdf_bytes,
        file_name="obbb_deduction_report.pdf",
        mime="application/pdf"
)
# -------------------------
# FOOTER
# -------------------------
st.markdown("---")

# Update version tracker
update_version_date = datetime.now().strftime('%Y-%m-%d')
st.caption(f"{t['footer']} • {update_version_date}")