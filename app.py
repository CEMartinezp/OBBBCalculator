import streamlit as st
import pandas as pd
from datetime import datetime
from logic import calculate_ot_premium, apply_phaseout

if "eligible_override" not in st.session_state:
    st.session_state.eligible_override = False

st.set_page_config(page_title="Calculadora Deducción Horas Extras 2025", layout="wide")

# ────────────────────────────────────────────────
# TEXTOS CLAROS Y AMIGABLES (todo en español sencillo)
# ────────────────────────────────────────────────
t = {
    "title": "Calculadora de Deducción por Horas Extras (Ley OBBB 2025)",
    "desc": "Estima cuánto de tu pago por horas extras puedes quitar de tus impuestos federales en 2025 (hasta $12,500 o $25,000 según tu situación). Solo aplica a la parte 'extra' que te pagan por trabajar más horas.",
    "flsa_title": "Paso 1: ¿Cumples con los requisitos básicos? (obligatorio)",
    "non_exempt_label": "¿Tu trabajo es de tipo 'no exento' de horas extras? (non-exempt)",
    "over_40_label": "¿Te pagan horas extras por trabajar más de 40 horas a la semana?",
    "ot_1_5x_label": "¿La mayoría de tus horas extras se pagan a tiempo y medio (1.5 veces tu tarifa normal)?",
    "unlock_message": "Según tus respuestas, es posible que no califiques automáticamente. Consulta con un contador antes de usar este número en tu declaración.",
    "override_button": "Sí califico y quiero continuar de todos modos",
    "override_success": "Has confirmado manualmente que calificas. ¡Sigamos!",
    "income_title": "Paso 2: Tus ingresos y datos de horas extras",
    "magi_label": "Ingreso total aproximado del año (incluye horas extras, bonos, etc.) ($)",
    "filing_label": "Tu situación al presentar impuestos",
    "filing_options": ["Soltero o Cabeza de Familia", "Casado presentando declaración conjunta"],
    "calc_button": "Calcular mi deducción estimada",
    "results_title": "Tus resultados",
    "footer": "Hecho por Carlos E. Martinez • {date} • Esta es solo una estimación – consulta a un profesional de impuestos",
    "answer_options": ["Sí", "No", "No estoy seguro"],
}

st.title(t["title"])
st.info(t["desc"])

# ────────────────────────────────────────────────
# ELEGIBILIDAD FLSA (con tooltips)
# ────────────────────────────────────────────────
with st.expander(t["flsa_title"], expanded=True):
    non_exempt = st.radio(
        t["non_exempt_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        help="La mayoría de los trabajadores por hora son 'no exentos'. Si tu empleador te paga horas extras obligatoriamente, probablemente sí lo eres."
    )
    over_40 = st.radio(
        t["over_40_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        help="¿Tu pago extra es porque superas las 40 horas semanales? (regla principal de la ley federal FLSA)"
    )
    ot_1_5x = st.radio(
        t["ot_1_5x_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        help="¿La mayor parte de tu pago extra es 1.5 veces tu tarifa normal? (time-and-a-half). Si es doble tiempo (2x) en algunos casos, igual puede calificar."
    )

    auto_eligible = (non_exempt == "Sí" and over_40 == "Sí" and ot_1_5x == "Sí")
    eligible = auto_eligible or st.session_state.eligible_override

    if eligible:
        st.success(t["override_success"] if st.session_state.eligible_override else "¡Perfecto! Cumples los requisitos básicos.")
    else:
        st.warning(t["unlock_message"])
        if st.button(t["override_button"]):
            st.session_state.eligible_override = True
            st.rerun()

# ────────────────────────────────────────────────
# SECCIÓN DE INGRESOS – TODO VISIBLE
# ────────────────────────────────────────────────
if eligible:
    st.subheader(t["income_title"])

    # Info general
    col_gen1, col_gen2 = st.columns([3, 2])
    with col_gen1:
        filing_status = st.selectbox(
            t["filing_label"],
            t["filing_options"],
            help="Elige cómo vas a presentar tu declaración de impuestos federales. Esto afecta el límite máximo de deducción."
        )
    with col_gen2:
        total_income = st.number_input(
            t["magi_label"],
            min_value=0.0,
            value=0.0,
            step=1000.0,
            help="Suma aproximada de todos tus ingresos del año (salario normal + horas extras + bonos + otros). Es similar a lo que aparece en la línea de ingreso bruto ajustado (MAGI)."
        )

    st.markdown("### Tus datos de horas extras")
    st.info("Llena **al menos una** de las dos opciones. Si llenas ambas, la calculadora usará el método de horas (más preciso).")

    col_left, col_right = st.columns(2)

    # ── Opción 1: Monto total pagado ──
    with col_left:
        st.subheader("Opción A – Monto total que te pagaron por horas extras")
        ot_total_paid = st.number_input(
            "Dinero TOTAL recibido por horas extras este año ($)",
            min_value=0.0,
            value=0.0,
            step=100.0,
            help="Mira tus talones de pago o tu W-2. Suma TODO lo que te pagaron por concepto de horas extras (incluye la parte que sería tu salario normal + el dinero adicional)."
        )

        ot_multiplier_str = st.radio(
            "La mayoría de tus horas extras se pagan a...",
            ["1.5 veces (tiempo y medio)", "2.0 veces (doble tiempo)"],
            horizontal=True,
            key="mult_total"
        )

        amount_included = st.radio(
            "¿Qué incluye el monto que acabas de escribir?",
            [
                "Todo junto: parte normal + el extra (lo más común en talones de pago)",
                "Solo el dinero ADICIONAL (la prima o el 'extra' que te pagan por ser horas extras)"
            ],
            horizontal=True,
            key="type_total",
            help="Ejemplo: hora normal $20 → overtime a $30. Si escribes $150 por 5 horas → es 'todo junto'. Si solo escribes los $50 extras → es 'solo el adicional'."
        )

    # ── Opción 2: Horas trabajadas + tarifa ──
    with col_right:
        st.subheader("Opción B – Horas trabajadas (más preciso si tienes los números)")
        regular_rate = st.number_input(
            "Tu tarifa horaria normal ($ por hora)",
            min_value=0.0,
            value=20.0,
            step=0.5,
            help="¿Cuánto te pagan por hora normal, sin extras?"
        )
        ot_hours_1_5 = st.number_input(
            "Horas totales en el año pagadas a tiempo y medio (1.5x)",
            min_value=0.0,
            value=0.0,
            step=5.0,
            help="Suma de todas las horas extras que te pagaron a 1.5 veces tu tarifa normal durante todo el año."
        )
        dt_hours_2_0 = st.number_input(
            "Horas totales en el año pagadas a doble tiempo (2.0x)",
            min_value=0.0,
            value=0.0,
            step=5.0,
            help="Suma de horas pagadas al doble (si aplica en tu trabajo, ej. domingos o más de cierto límite)."
        )

    # ────────────────────────────────────────────────
    # BOTÓN CALCULAR + LÓGICA
    # ────────────────────────────────────────────────
    if st.button(t["calc_button"], type="primary", width='stretch'):
        use_hours = (regular_rate > 0 and (ot_hours_1_5 + dt_hours_2_0) > 0)

        if use_hours:
            # Método horas (prioridad)
            premium_1_5 = ot_hours_1_5 * regular_rate * 0.5
            premium_2_0 = dt_hours_2_0 * regular_rate * 1.0
            method_used = "Por horas trabajadas (más preciso)"
            ot_total_shown = (ot_hours_1_5 * regular_rate * 1.5) + (dt_hours_2_0 * regular_rate * 2.0)
            base_salary_est = total_income - ot_total_shown if ot_total_shown > 0 else total_income

        elif ot_total_paid > 0:
            # Método monto
            is_total_combined = "todo junto" in amount_included.lower()
            multiplier = 1.5 if "1.5" in ot_multiplier_str else 2.0
            amount_type = "total" if is_total_combined else "premium"
            premium_1_5 = calculate_ot_premium(ot_total_paid, multiplier, amount_type)
            premium_2_0 = 0.0
            method_used = f"Por monto total ({'todo junto' if is_total_combined else 'solo extra'})"
            ot_total_shown = ot_total_paid
            base_salary_est = total_income - ot_total_paid if is_total_combined else total_income
        else:
            st.error("Por favor, completa al menos una de las dos opciones de horas extras para poder calcular.")
            st.stop()

        qoc_gross = premium_1_5 + premium_2_0

        # Phaseout según reglas reales 2025
        is_joint = filing_status == t["filing_options"][1]
        max_deduction = 25000 if is_joint else 12500
        phase_start = 300000 if is_joint else 150000
        # Nota: phaseout completo ~ $125,000 adicional (de $150k a $275k single, etc.)
        final_deduction = max(0.0, apply_phaseout(total_income, max_deduction, phase_start))
        reduction_amount = max(0.0, qoc_gross - final_deduction)

        # ────────────────────────────────────────────────
        # RESULTADOS EN TABS
        # ────────────────────────────────────────────────
        tab_data, tab_results = st.tabs(["📋 Datos que ingresaste", "📊 Resultados y deducción"])

        with tab_data:
            st.subheader("Resumen de lo que ingresaste")
            data_summary = {
                "Concepto": [
                    "Situación al declarar impuestos",
                    "Ingreso total aproximado del año",
                    "Salario base estimado (sin extras)",
                    "Total pagado por horas extras",
                    "Parte extra 1.5x (deducible)",
                    "Parte extra 2.0x (deducible)",
                    "Método usado",
                    "¿No exento?",
                    "¿Horas extras >40h/sem?",
                    "¿Principalmente 1.5x?"
                ],
                "Valor": [
                    filing_status,
                    f"${total_income:,.0f}",
                    f"${base_salary_est:,.0f}",
                    f"${ot_total_shown:,.0f}",
                    f"${premium_1_5:,.0f}",
                    f"${premium_2_0:,.0f}",
                    method_used,
                    non_exempt,
                    over_40,
                    ot_1_5x
                ]
            }
            st.dataframe(pd.DataFrame(data_summary), width='stretch', hide_index=True)

        with tab_results:
            st.subheader(t["results_title"])

            col_left_res, col_right_res = st.columns([1, 2])

            with col_left_res:
                st.metric("**Deducción final estimada (Línea 14a)**", f"${final_deduction:,.0f}")
                st.success("Esta es la cantidad aproximada que podrías quitar de tus ingresos gravables.")

            with col_right_res:
                st.subheader("Desglose detallado")
                st.metric("Parte extra por tiempo y medio (1.5x)", f"${premium_1_5:,.0f}")
                st.metric("Parte extra por doble tiempo (2.0x)", f"${premium_2_0:,.0f}")
                st.metric("Total extra antes de límites", f"${qoc_gross:,.0f}")
                if reduction_amount > 0:
                    st.metric("Reducción porque el ingreso es alto", f"-${reduction_amount:,.0f}")

            if reduction_amount > 0:
                st.markdown("**Cómo se reduce la deducción:**")
                chart_data = pd.DataFrame({
                    "Categoría": ["Total extra posible", "Deducción final permitida"],
                    "Monto ($)": [qoc_gross, final_deduction]
                })
                st.bar_chart(chart_data.set_index("Categoría"))

# Footer
st.markdown("---")
st.caption(t["footer"].format(date=datetime.now().strftime("%Y-%m-%d")))