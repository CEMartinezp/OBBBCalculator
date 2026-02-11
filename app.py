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
        "title": "Calculadora QOC – Línea 14a (OBBB 2025)",
        "desc": "Calcula tu deducción por horas extras calificadas (QOC) según la Ley OBBB 2025.",
        "flsa_title": "0. Elegibilidad FLSA Section 7 (obligatorio)",
        "non_exempt_label": "¿Eres empleado non-exempt?",
        "over_40_label": "¿Tu overtime es por >40 horas por semana?",
        "ot_1_5x_label": "¿El overtime es principalmente a 1.5x?",
        "unlock_message": "Responde **Sí** a las tres preguntas para desbloquear la calculadora.",
        "override_button": "Confirmo que califico y quiero continuar",
        "override_success": "Has confirmado manualmente que calificas.",
        "income_title": "1. Información de Ingresos",
        "magi_label": "MAGI estimado ($)",
        "filing_label": "Estado civil",
        "filing_options": ["Soltero / Cabeza de familia", "Casado declarando conjuntamente"],
        "input_method_label": "¿Cómo quieres ingresar tus datos de overtime?",
        "input_method_options": [
            "Por monto total pagado (más fácil)",
            "Por horas trabajadas + tarifa horaria (más preciso)"
        ],
        "ot_label": "Monto total pagado por Overtime ($)",
        "ot_help": "Suma de todo lo que te pagaron por overtime (base + prima).",
        "regular_rate_label": "Tarifa horaria regular ($)",
        "ot_hours_label": "Horas anuales de Overtime (1.5x)",
        "dt_hours_label": "Horas anuales de Double Time (2.0x)",
        "calc_button": "Calcular QOC",
        "results_title": "Resultados",
        "income_summary": "Resumen de Ingresos",
        "benefits_breakdown": "Desglose de Beneficios OBBB",
        "qoc_final": "QOC Deducción Final (Línea 14a)",
        "footer": "Hecho por Carlos E. Martinez • {date}",
        "answer_options": [
            "Si",
            "No",
            "No se"
        ],
        "non_exempt_label": "¿Eres empleado non-exempt (no exento de overtime)?",
        "over_40_label": "¿Tu overtime se paga por trabajar más de 40 horas por semana?",
        "ot_1_5x_label": "¿El overtime que recibes es principalmente a 1.5x (time-and-a-half)?"
    },
}

language = st.selectbox("Idioma / Language", ["Español"], index=0)
lang = "es" if language == "Español" else "es"
t = texts[lang]

st.title(t["title"])
st.info(t["desc"])

# ────────────────────────────────────────────────
# ELEGIBILIDAD FLSA
# ────────────────────────────────────────────────
with st.expander(t["flsa_title"], expanded=True):
    non_exempt = st.radio(t["non_exempt_label"], t["answer_options"], index=2, horizontal=True)
    over_40    = st.radio(t["over_40_label"],    t["answer_options"], index=2, horizontal=True)
    ot_1_5x    = st.radio(t["ot_1_5x_label"],    t["answer_options"], index=2, horizontal=True)

    auto_eligible = (non_exempt == t["answer_options"][0] and over_40 == t["answer_options"][0]and ot_1_5x == t["answer_options"][0])
    eligible = auto_eligible or st.session_state.eligible_override

    if eligible:
        st.success(t["override_success"] if st.session_state.eligible_override else "Elegibilidad FLSA confirmada.")
    else:
        st.warning(t["unlock_message"])
        if st.button(t["override_button"]):
            st.session_state.eligible_override = True
            st.rerun()

# ────────────────────────────────────────────────
# DATOS PRINCIPALES (solo si eligible)
# ────────────────────────────────────────────────
if eligible:
    with st.expander(t["income_title"], expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            magi = st.number_input(t["magi_label"], min_value=0.0, value=0.0, step=1000.0)
            filing_status = st.selectbox(t["filing_label"], t["filing_options"])
        
        with col2:
            input_method = st.radio(t["input_method_label"], t["input_method_options"], index=0)

        # ── Método 1: Monto total ──
        if input_method == t["input_method_options"][0]:
            ot_total = st.number_input(t["ot_label"], min_value=0.0, value=0.0, step=100.0, help=t["ot_help"])
            ot_multiplier_str = st.radio("Multiplicador principal", ["1.5x", "2.0x"], horizontal=True)
            ot_multiplier = 1.5 if ot_multiplier_str == "1.5x" else 2.0
            ot_is_total = st.radio("Tipo de monto", ["Total combinado", "Solo prima"], horizontal=True)
            amount_type = "total" if ot_is_total == "Total combinado" else "premium"

        # ── Método 2: Horas + Tarifa ──
        else:
            regular_rate = st.number_input("Tarifa horaria regular ($)", min_value=0.0, value=20.0, step=0.5)
            ot_hours = st.number_input(t["ot_hours_label"], min_value=0.0, value=0.0, step=10.0)
            dt_hours = st.number_input(t["dt_hours_label"], min_value=0.0, value=0.0, step=10.0)
            ot_multiplier = 1.5  # Por defecto para este método

    # ────────────────────────────────────────────────
    # Botón calcular
    # ────────────────────────────────────────────────
    if st.button(t["calc_button"], type="primary", use_container_width=True):
        if input_method == t["input_method_options"][0]:
            # Método por monto
            ot_premium = calculate_ot_premium(ot_total, ot_multiplier, amount_type)
            dt_premium = 0.0
            method = f"{amount_type} ({ot_multiplier}x)"
        else:
            # Método por horas + tarifa
            ot_premium = ot_hours * regular_rate * 0.5          # Prima 1.5x = 0.5 × rate
            dt_premium = dt_hours * regular_rate * 1.0          # Prima 2.0x = 1.0 × rate
            method = "Cálculo por horas + tarifa"

        qoc_raw = ot_premium + dt_premium

        # Phaseout
        # Definir límites según estado civil
        if filing_status == t["filing_options"][1]:
            max_qoc = 25000
            phase_start = 300000
        else:
            max_qoc = 12500
            phase_start = 150000
            
        # Calcular deducción después de phaseout
        qoc_ded = apply_phaseout(magi, max_qoc, phase_start)

        # Asegurarse de que no sea negativa
        qoc_ded = max(0.0, qoc_ded)

        # Reducción = cuánto se quitó (nunca negativo)
        reduccion_por_phaseout = max(0.0, qoc_raw - qoc_ded)
    
        # ────────────────────────────────────────────────
        # RESULTADOS
        # ────────────────────────────────────────────────
        st.subheader(t["results_title"], text_alignment="center")

        col_sum, col_break = st.columns([1, 2])

        with col_sum:
            st.subheader(t["income_summary"])
            st.write(f"**MAGI**: ${magi:,.0f}")
            st.write(f"**Estado civil**: {filing_status}")
            st.write(f"**Método usado**: {method}")

        with col_break:
            st.subheader(t["benefits_breakdown"])
            st.metric("Prima Overtime 1.5x", f"${ot_premium:,.0f}")
            st.metric("Prima Double Time 2.0x", f"${dt_premium:,.0f}")
            st.metric("Total QOC Bruto", f"${qoc_raw:,.0f}")
            st.metric("Reducción por Phaseout", f"${reduccion_por_phaseout:,.0f}")
            st.success(f"**QOC Deducción Final (Línea 14a)**: ${qoc_ded:,.0f}")
        
# Footer
st.markdown("---")
st.caption(t["footer"].format(date=datetime.now().strftime("%Y-%m-%d")))