import streamlit as st
from datetime import datetime
from logic import calculate_ot_premium, apply_phaseout

if "eligible_override" not in st.session_state:
    st.session_state.eligible_override = False


st.set_page_config(page_title="Calculadora QOC OBBB 2025", layout="centered")

# ────────────────────────────────────────────────
# TEXTOS BILINGÜES (con instrucciones ampliadas)
# ────────────────────────────────────────────────
texts = {
    "es": {
        "title": "Calculadora QOC – Línea 14a Schedule 1 (OBBB 2025)",
        "desc": "Calcula el monto de Qualified Overtime Compensation (QOC) reportable en la Línea 14a del Schedule 1 (Form 1040).\nSolo califica overtime bajo FLSA Section 7 (non-exempt, >40 h/semana, principalmente 1.5x).",
        "flsa_title": "0. Elegibilidad FLSA Section 7 (obligatorio)",
        "non_exempt_label": "¿Eres empleado non-exempt (no exento de overtime)?",
        "over_40_label": "¿Tu overtime se paga por trabajar más de 40 horas por semana?",
        "ot_1_5x_label": "¿El overtime que recibes es principalmente a 1.5x (time-and-a-half)?",
        "unlock_message": "Responde **Sí** a las tres preguntas anteriores para desbloquear los campos.\nSi estás seguro de que calificas aunque alguna respuesta no sea Sí, usa el botón de abajo.",
        "unlocked_message": "Elegibilidad FLSA confirmada.",
        "override_button": "Confirmo que califico y quiero continuar",
        "override_success": "Has confirmado manualmente que calificas. La calculadora está desbloqueada.",
        "no_override_success": "Elegibilidad FLSA confirmada.",
        "income_title": "1. Información de ingresos y nómina",
        "income_title": "1. Información de ingresos y nómina",
        "ot_label": "Monto total de Overtime ($)",
        "ot_help": """**Qué coloco aquí**: Suma de TODO el dinero recibido por overtime durante todo el año (incluye la parte regular + la prima extra).\n
        **Ejemplo**: Si trabajaste 10 horas OT a 1.5x y tu rate es $20/h → pago OT = $300 (10×$20 + 10×$10 prima) → ingresa 300.\n
        **Cómo consigo esta información**:\n• Busca en cada pay stub: Earnings → "Overtime", "OT Pay", "Premium OT"\n• Suma el monto YTD de overtime de todos los talones del año\n• Si solo tienes un resumen anual: usa el total YTD directamente.\n
        **Cómo verifico**:\n• Si tu pay stub solo muestra OT total combinado → QOC ≈ OT / 3 (para 1.5x)\n• Compara con horas × rate × 1.5 (debería aproximarse).""",
        "multiplier_label": "Multiplicador de horas extras",
        "multiplier_options": ["1.5 (Tiempo y medio)", "2.0 (doble tiempo)"],
        "multiplier_help": "Selecciona el multiplicador más común en tus pagos de overtime.\n• 1.5 = tiempo y medio (lo que exige FLSA)\n• 2.0 = doble tiempo (puede ser por ley estatal o acuerdo)\nSolo estos dos valores están permitidos para cumplir con las reglas de QOC.",
        "ot_is_total_label": "¿El monto de OT que ingresaste es total combinado o solo la prima?",
        "ot_is_total_options": ["Total combinado (base + prima)", "Solo prima", "No sé"],
        "ot_is_total_help": "Importante para calcular correctamente la parte deducible:\n• Total combinado → la calculadora divide entre 3 o 4 para obtener solo la prima\n• Solo prima → se usa directamente\n• No sé → se asume total combinado (más conservador)",
        "dt_has_label": "¿Tu pay stub tiene línea separada de Double Time / DT?",
        "dt_total_label": "Monto Total de Time Doble ($)",
        "dt_total_help": """**Qué coloco aquí**: El monto en dólares que aparece en la línea de Double Time (si está separada).\n
        **Cómo consigo esta información**: Pay stub → Earnings → "Double Time", "DT", "DT Pay" → mira el monto YTD y súmalo si es necesario.\n
        **Cómo verifico**: Si es monto total → QOC ≈ monto / 4\nCompara también con: horas DT × tu rate regular × 2.""",
        "dt_hours_label": "Horas de Tiempo Doble (anual)",
        "dt_hours_help": """**Qué coloco aquí**: Cantidad total de horas pagadas a doble tarifa durante todo el año.\n
        **Cómo consigo esta información**: Pay stub → Earnings → "Double Time" o "DT" → columna de HORAS (no dólares) → suma YTD si es necesario.\n
        **Cómo verifico**: Multiplica tus horas DT por tu tarifa regular y por 2 → debe acercarse al monto que pagaron por DT.""",
        "calc_button": "Calcular QOC para Línea 14a",
        "results_title": "Resultados – Schedule 1-A Línea 14a",
        "qoc_final": "Compensación por horas extraordinarias calificadas a reportar (QOC en Ingles)",
        "method": "Método usado",
        "y": "Sí",
        "n": "No",
        "idk": "No sé",
        "footer": "Hecho por Carlos E. Martinez • {date}",
        "magi_label": "IBAM estimado ($)",
        "magi_help": "ingreso bruto ajustado modificado (IBAM o MAGI en Ingles) aproximado para el año.\nUsa tu estimación de ingreso bruto ajustado (W-2 Box 1 + otros ingresos - deducciones).",
        "filing_label": "Estado civil para impuestos",
        "filing_options": ["Soltero / Cabeza de familia", "Casado declarando conjuntamente"],
            "qoc_raw": "Prima bruta calculada",
    },
    "en": {
        "title": "QOC Calculator – Schedule 1 Line 14a (OBBB 2025)",
        "desc": "Calculate Qualified Overtime Compensation (QOC) for Schedule 1 (Form 1040) Line 14a.\nOnly FLSA Section 7 overtime qualifies.",
        "flsa_title": "0. FLSA Section 7 Eligibility (required)",
        "non_exempt_label": "Are you non-exempt (eligible for overtime)?",
        "over_40_label": "Is overtime paid for hours over 40 per week?",
        "ot_1_5x_label": "Is overtime primarily at 1.5x (time-and-a-half)?",
        "warning_not_qualified": "⚠️ WARNING: To qualify for the OBBB deduction, you must answer **Yes** to all three eligibility questions above.",
        "unlock_message": "Answer **Yes** to all three FLSA eligibility questions to unlock the fields and calculate.",
        "unlocked_message": "Confirmed FLSA eligibility .",
        "override_button": "I confirm that I qualify and want to continue",
        "override_success": "You have manually confirmed that you caliphate. The calculator is unlocked.",
        "no_override_success": "Elegibilidad FLSA confirmed.",
        "income_title": "1. Income & Payroll Information",
        "ot_label": "Total Overtime Pay ($)",
        "ot_help":  """**What do I put here**: Sum of ALL the money received overtime throughout the year (includes the regular part + the extra premium).\n **Example**: If you worked 10 OT hours at 1.5x and your rate is $20/h → OT payment = $300 (10×$20 + 10×$10 premium) → enter 300.\n **How do I get this information**:\n• Search each pay stub: Earnings → "Overtime", "OT Pay", "Premium OT"\n• Add the YTD amount of overtime of all stubs for the year\n• If you only have an annual summary: use the total YTD directly.\n **How do I check**:\n• If your pay stub only shows combined total OT → QOC ≈ OT /3 (for 1.5x)\n• Compare with hours × rate × 1.5 (should be approximated).""",
        "multiplier_label": "Overtime Multiplier",
        "multiplier_options": ["1.5 (time-and-a-half)", "2.0 (double time)"],
        "ot_is_total_label": "Is OT amount total combined or premium only?",
        "ot_is_total_options": ["Total combined (base + premium)", "Premium only", "Don't know"],
        "ot_is_total_help": "Important to correctly calculate the deductible part:\n• Combined total → the calculator divides by 3 or 4 to obtain only the premium\n• Only premium → directly used\n• I don't know → total combined is assumed (more conservative)",
        "dt_has_label": "Does your pay stub have separate Double Time / DT line?",
        "dt_total_label": "Double Time Total Amount ($)",
        "dt_total_help": """**What do I put here**: The dollar amount that appears on the Double Time line (if separate).\n **How do I get this information**: Pay stub → Earnings → "Double Time", "DT", "DT Pay" → look at the YTD amount and add it if necessary.\n **How do I verify**: If it is total amount → QOC ≈ amount / 4\nAlso compare with: DT hours × your regular rate × 2.""",
        "dt_hours_label": "Double Time Hours (annual)",
        "dt_hours_help": """**What do I put here**: Total number of hours paid at double rate throughout the year.\n **How do I get this information**: Pay stub → Earnings → "Double Time" or "DT" → HOURS column (not dollars) → add YTD if necessary.\n **How do I verify**: Multiply your DT hours by your regular rate and by 2 → should be close to the amount you paid per DT.""",
        "calc_button": "Calculate QOC for Line 14a",
        "results_title": "Results – Schedule 1-A Line 14a",
        "qoc_final": "Qualified Overtime Compensation (QOC) to report",
        "method": "Method used",
        "validation": "Validation",
        "y": "Yes",
        "n": "No",
        "idk": "Don't know",
        "footer": "Made by Carlos E. Martinez • {date}",
        "magi_label": "Modified Adjusted Gross Income (MAGI) (before overtime) ($)",
        "magi_help": "Approximate modified adjusted gross income (MAGI) for the year.\n Use your adjusted gross income estimate (W-2 Box 1 + other income - deductions).",
        "filing_label": "Civil status for taxes",
        "filing_options": ["Single/Head of household", "Married jointly declaring"],
        "qoc_raw": "Calculated gross premium",
    }
}

language = st.selectbox("Idioma / Language", ["Español", "English"], index=0)
lang = "es" if language == "Español" else "en"
t = texts[lang]

st.title(t["title"])
st.info(t["desc"])

# ────────────────────────────────────────────────
# Preguntas FLSA
# ────────────────────────────────────────────────
with st.expander(t["flsa_title"], expanded=True):
    non_exempt = st.radio(t["non_exempt_label"], [t["y"], t["n"], t["idk"]], index=2, horizontal=True)
    over_40    = st.radio(t["over_40_label"],    [t["y"], t["n"], t["idk"]], index=2, horizontal=True)
    ot_1_5x    = st.radio(t["ot_1_5x_label"],    [t["y"], t["n"], t["idk"]], index=2, horizontal=True)

    auto_eligible = (non_exempt == t["y"] and over_40 == t["y"] and ot_1_5x == t["y"])
    eligible = auto_eligible or st.session_state.eligible_override

    if eligible:
        st.success(t["override_success"] if st.session_state.eligible_override else "Elegibilidad FLSA confirmada.")
    else:
        st.warning(t["unlock_message"])
        if st.button(t["override_button"]):
            st.session_state.eligible_override = True
            st.rerun()

# ────────────────────────────────────────────────
# Sección de ingresos – deshabilitada hasta que sea eligible
# ────────────────────────────────────────────────
if eligible:
    with st.expander(t["income_title"], expanded=True):
        magi = st.number_input(t["magi_label"], min_value=0.0, value=0.0, step=1000.0, help=t["magi_help"])

        filing_status = st.selectbox(t["filing_label"], t["filing_options"])
        
        ot_total = st.number_input(t["ot_label"], min_value=0.0, value=0.0, step=100.0, help=t["ot_help"])
        
        ot_multiplier_str = st.radio(t["multiplier_label"], t["multiplier_options"])
        ot_multiplier = 1.5 if ot_multiplier_str == t["multiplier_options"][0] else 2.0
        
        # ── Double Time condicional ──
        has_dt = st.checkbox(t["dt_has_label"])

        dt_total = dt_hours = 0.0
        if has_dt:
            col1, col2 = st.columns(2)
            with col1:
                dt_total = st.number_input(t["dt_total_label"], min_value=0.0, value=0.0, step=50.0, help=t["dt_total_help"])
            with col2:
                dt_hours = st.number_input(t["dt_hours_label"], min_value=0.0, value=0.0, step=1.0, help=t["dt_hours_help"])

        ot_is_total = st.radio(t["ot_is_total_label"], t["ot_is_total_options"], help=t["ot_is_total_help"])

    # ────────────────────────────────────────────────
    # Botón calcular
    # ────────────────────────────────────────────────
    if st.button(t["calc_button"], type="primary", use_container_width=True):
        amount_type = "total" if ot_is_total == t["ot_is_total_options"][0] else "premium" if ot_is_total == t["ot_is_total_options"][1] else "unknown"

        ot_premium = calculate_ot_premium(ot_total, ot_multiplier, amount_type)

        dt_premium = (dt_total / 4) if dt_total > 0 else (dt_hours * 1.0 if dt_hours > 0 else 0)

        qoc_raw = ot_premium + dt_premium

        # Phaseout
        max_qoc = 25000 if filing_status == t["filing_options"][1] else 12500
        phase_start = 300000 if filing_status == t["filing_options"][1] else 150000

        qoc_ded = apply_phaseout(magi, max_qoc, phase_start)

        method = f"{amount_type} + DT" if dt_premium > 0 else amount_type

        st.subheader(t["results_title"])
        st.success(f"**{t['qoc_final']}: ${qoc_ded:,.0f}**")
        st.metric(t["method"], method)
        st.metric(t["qoc_raw"], f"${qoc_raw:,.0f}")
        
# Footer
st.markdown("---")
st.caption(t["footer"].format(date=datetime.now().strftime("%Y-%m-%d")))