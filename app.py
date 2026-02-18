import streamlit as st
import pandas as pd
from datetime import datetime
from logic import calculate_ot_premium, apply_phaseout

# ────────────────────────────────────────────────
# CONFIGURACIÓN INICIAL
# ────────────────────────────────────────────────
if "eligible_override" not in st.session_state:
    st.session_state.eligible_override = False

st.set_page_config(
    page_title="Calculadora Deducción Horas Extras 2025",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ────────────────────────────────────────────────
# TEXTOS COMPLETOS – TODO AQUÍ (incluyendo frases nuevas)
# ────────────────────────────────────────────────
texts = {
    "es": {
        # Principales
        "title": "Calculadora de Deducción por Horas Extras (Ley OBBB 2025)",
        "desc": "Estima cuánto dinero extra de tus horas extras puedes quitar de tus impuestos federales en 2025 (hasta \\$12,500 o \\$25,000 según tu situación).",
        "flsa_title": "Paso 1: ¿Cumples con los requisitos básicos? (obligatorio)",
        "non_exempt_label": "¿Tu trabajo es de tipo 'no exento' de horas extras? (non-exempt)",
        "over_40_label": "¿Te pagan horas extras por trabajar más de 40 horas a la semana?",
        "ot_1_5x_label": "¿La mayoría de tus horas extras se pagan a tiempo y medio (1.5 veces tu tarifa normal)?",
        "unlock_message": "Según tus respuestas, es posible que no califiques automáticamente. Consulta con un contador antes de usar esta calculadora. Si aun deseas proseguir, haz click abajo para confirmar que calificas de todos modos",
        "override_button": "Sí califico y quiero continuar de todos modos",
        "override_success": "¡Genial! Has confirmado manualmente que calificas.",
        "income_title": "Paso 2: Ingresa tus datos de ingresos y horas extras",
        "magi_label": "Tu ingreso total aproximado del año (incluye horas extras, bonos, etc.) (\\$)",
        "filing_label": "Tu situación al presentar impuestos",
        "filing_options": ["Soltero o Cabeza de Familia", "Casado presentando declaración conjunta"],
        "calc_button": "Calcular mi deducción estimada",
        "results_title": "Tus resultados estimados",
        "footer": "Hecho por Carlos E. Martinez • {date} • Esta es solo una estimación – consulta siempre a un profesional de impuestos",
        "answer_options": ["Sí", "No", "No estoy seguro"],

        # Mensajes de ayuda FLSA (faltaban)
        "flsa_non_exempt_help": "La mayoría de los trabajos por hora son 'no exentos'. Si tu jefe te paga horas extras por ley, probablemente sí.",
        "flsa_over_40_help": "¿Te pagan más cuando superas las 40 horas por semana? Eso es la regla principal.",
        "flsa_ot_1_5x_help": "¿Casi todo tu pago extra es 1.5 veces tu tarifa normal? (ej: \\$30 en vez de \\$20). Si es doble en algunos días, igual puede contar.",

        # Ejemplo y pasos
        "example_title": "**Ejemplo:**",
        "example_text": """
        - Tu tarifa normal: **\\$25 por hora**  
        - Trabajas **10 horas extras** a 1.5x → te pagan **\\$375 total** (\\$250 de base + **\\$125 de dinero extra**)  
        - **Opción A**: Escribe **\\$375** y elige "Todo junto"  
        - **Opción B**: Escribe tarifa **\\$25** y 10 horas a 1.5x
        """,
        "step3_title": "Paso 3: Tus datos de horas extras",
        "step3_info": "**Llena al menos una opción**. Si llenas las dos, usaremos la Opción B.",

        # Opción A y B
        "option_a_title": "**Opción A** (por monto total pagado)",
        "ot_total_paid_label": "Dinero TOTAL que te pagaron por horas extras este año (\\$)",
        "ot_total_paid_help": "Revisa tus recibos de pago o W-2. Suma **todo** lo recibido por horas extras.",
        "ot_multiplier_label": "La mayoría de tus horas extras se pagan a...",
        "ot_multiplier_options": ["1.5 veces (tiempo y medio)", "2.0 veces (doble tiempo)"],
        "amount_included_label": "El monto que escribiste por horas extras, ¿incluye...?",
        "amount_included_options": [
            "Todo lo que recibí (parte normal + el dinero extra adicional)",
            "Solo el dinero extra adicional (el pago por ser horas extras)"
        ],
        "amount_included_help": "Especifica si descontaste el pago base en el monto que colocaste.",
        "option_b_title": "**Opción B** (por horas trabajadas)",
        "regular_rate_label": "Tu tarifa horaria normal (\\$ por hora)",
        "regular_rate_help": "¿Cuánto te pagan normalmente por una hora, sin extras?",
        "ot_hours_1_5_label": "Horas totales en el año pagadas a tiempo y medio (1.5x)",
        "ot_hours_1_5_help": "Suma de **todas** las horas extras que te pagaron a 1.5 veces durante el año.",
        "dt_hours_2_0_label": "Horas totales en el año pagadas a doble tiempo (2.0x)",
        "dt_hours_2_0_help": "Horas pagadas al doble (ej: fines de semana o turnos especiales).",

        # Errores y métodos
        "error_no_data": "⚠️ Completa al menos una de las opciones para calcular.",
        "method_hours": "Por horas trabajadas (Opcion B)",
        "method_total_combined": "Por monto total (Opcion A)",
        "method_total_premium": "Por monto total (solo dinero extra)",

        # Resumen de datos
        "data_tab_title": "Resumen de tus datos",
        "data_subtitle": "Lo que ingresaste",
        "data_concepts": [
            "Situación al declarar impuestos",
            "Ingreso total aproximado del año",
            "Salario base estimado (sin extras)",
            "Total pagado por horas extras",
            "Pago adicional 1.5x (deducible)",
            "Pago adicional 2.0x (deducible)",
            "Método usado",
            "¿No exento?",
            "¿Horas extras >40h/sem?",
            "¿Principalmente 1.5x?"
        ],

        # Resultados – TODAS LAS CLAVES NUEVAS INCLUIDAS
        "results_tab_title": "Resultados y deducción",
        "deduction_real_label": "**Deducción real que puedes usar** (Línea 14a)",
        "deduction_real_delta": "Este es el monto final a restar de tus impuestos",
        "deduction_real_success": "Esta es la cantidad que realmente puedes deducir en tu declaración. 🎉",
        "deduction_real_no_limit": "**Puedes deducir ${}** por el dinero adicional que ganaste en horas extras. (No hay límite aplicado en tu caso)",
        "deduction_real_with_limit": "**Puedes deducir ${}** por horas extras (limitado por tu ingreso total).",
        "limit_info": "Tu pago adicional por overtime fue de ${}, pero según tu ingreso total el máximo que puedes deducir es ${}. Por eso se reduce a esta cantidad.",
        "breakdown_subtitle": "Desglose detallado",
        "qoc_gross_label": "Dinero adicional ganado por horas extras (1.5x + 2.0x)",
        "phaseout_limit_label": "Límite máximo permitido por tu ingreso total",
        "reduction_label": "Reducción aplicada",
        "final_after_limit_label": "**Deducción final después de comparar ambos valores**",
        "chart_title": "**Comparación visual (lo que ganaste vs. lo que puedes deducir):**",
        "chart_caption": "La deducción que puedes reclamar es el menor valor entre lo que te pagaron de más por horas extras y el límite máximo que permite la ley según tu ingreso total.",
        "chart_categories": ["Dinero adicional por overtime", "Límite por ingresos", "Deducción final"],
        "chart_money_column": "Monto ($)"
    }
}

# Idioma
language = st.selectbox("🌐 Idioma", ["Español"], index=0, label_visibility="collapsed")
lang = "es"
t = texts[lang]

# ────────────────────────────────────────────────
# FORMATO DINERO
# ────────────────────────────────────────────────
def format_money(value):
    if value is None or value <= 0:
        return "$0"
    formatted = f"{int(value):,}"
    formatted = formatted.replace(",", ".")
    return f"${formatted}"

# ────────────────────────────────────────────────
# TÍTULO Y DESCRIPCIÓN
# ────────────────────────────────────────────────
st.title(t["title"])
st.info(t["desc"])

# ────────────────────────────────────────────────
# ELEGIBILIDAD FLSA – BLOQUEADA DESPUÉS DE CALIFICAR
# ────────────────────────────────────────────────
eligible = st.session_state.eligible_override

with st.expander(t["flsa_title"], expanded=not eligible):
    non_exempt = st.radio(
        t["non_exempt_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["flsa_non_exempt_help"]
    )
    over_40 = st.radio(
        t["over_40_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["flsa_over_40_help"]
    )
    ot_1_5x = st.radio(
        t["ot_1_5x_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["flsa_ot_1_5x_help"]
    )

    auto_eligible = (non_exempt == t["answer_options"][0] and 
                     over_40 == t["answer_options"][0] and 
                     ot_1_5x == t["answer_options"][0])

    eligible = auto_eligible or st.session_state.eligible_override

    if eligible:
        if st.session_state.eligible_override:
            st.success(t["override_success"])
            st.info("**Las respuestas de elegibilidad están bloqueadas.** Ya confirmaste manualmente que calificas. Si necesitas cambiarlas, usa el botón de abajo.")
        else:
            st.success("¡Excelente! Cumples los requisitos automáticamente.")
        
        if st.button("🔄 Reiniciar respuestas de elegibilidad", type="secondary", width='stretch'):
            st.session_state.eligible_override = False
            st.rerun()
    else:
        st.warning(t["unlock_message"])
        if st.button(t["override_button"], width='stretch'):
            st.session_state.eligible_override = True
            st.rerun()

# ────────────────────────────────────────────────
# SECCIÓN DE INGRESOS
# ────────────────────────────────────────────────
if eligible:
    st.subheader(t["income_title"])
    filing_status = st.selectbox(t["filing_label"], t["filing_options"])
    total_income = st.number_input(
        t["magi_label"],
        min_value=0.0,
        value=0.0,
        step=1000.0
    )

    st.markdown(f"### {t['step3_title']}")
    st.info(t["step3_info"])
    with st.expander(t["example_title"], expanded=False):
        st.markdown(t["example_text"])

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader(t["option_a_title"])
        ot_total_paid = st.number_input(
            t["ot_total_paid_label"],
            min_value=0.0,
            value=0.0,
            step=100.0,
            help=t["ot_total_paid_help"]
        )
        ot_multiplier_str = st.radio(
            t["ot_multiplier_label"],
            t["ot_multiplier_options"],
            horizontal=True,
            key="mult_total"
        )
        amount_included = st.radio(
            t["amount_included_label"],
            t["amount_included_options"],
            horizontal=True,
            key="type_total",
            help=t["amount_included_help"]
        )

    with col_right:
        st.subheader(t["option_b_title"])
        regular_rate = st.number_input(
            t["regular_rate_label"],
            min_value=0.0,
            value=20.0,
            step=0.5,
            help=t["regular_rate_help"]
        )
        ot_hours_1_5 = st.number_input(
            t["ot_hours_1_5_label"],
            min_value=0.0,
            value=0.0,
            step=5.0,
            help=t["ot_hours_1_5_help"]
        )
        dt_hours_2_0 = st.number_input(
            t["dt_hours_2_0_label"],
            min_value=0.0,
            value=0.0,
            step=5.0,
            help=t["dt_hours_2_0_help"]
        )

    # ────────────────────────────────────────────────
    # CÁLCULO
    # ────────────────────────────────────────────────
    if st.button(t["calc_button"], type="primary", width='stretch'):
        use_hours = (regular_rate > 0 and (ot_hours_1_5 + dt_hours_2_0) > 0)

        if use_hours:
            payment_additional_1_5 = ot_hours_1_5 * regular_rate * 0.5
            payment_additional_2_0 = dt_hours_2_0 * regular_rate * 1.0
            method_used = t["method_hours"]
            ot_total_shown = (ot_hours_1_5 * regular_rate * 1.5) + (dt_hours_2_0 * regular_rate * 2.0)
            base_salary_est = total_income - ot_total_shown if ot_total_shown > 0 else total_income
        elif ot_total_paid > 0:
            is_total_combined = "todo" in amount_included.lower() or "junto" in amount_included.lower()
            multiplier = 1.5 if "1.5" in ot_multiplier_str else 2.0
            amount_type = "total" if is_total_combined else "premium"
            payment_additional_1_5 = calculate_ot_premium(ot_total_paid, multiplier, amount_type)
            payment_additional_2_0 = 0.0
            method_used = t["method_total_combined"] if is_total_combined else t["method_total_premium"]
            ot_total_shown = ot_total_paid
            base_salary_est = total_income - ot_total_paid if is_total_combined else total_income
        else:
            st.error(t["error_no_data"])
            st.stop()

        qoc_gross = payment_additional_1_5 + payment_additional_2_0

        is_joint = filing_status == t["filing_options"][1]
        max_deduction = 25000 if is_joint else 12500
        phase_start = 300000 if is_joint else 150000
        final_deduction = max(0.0, apply_phaseout(total_income, max_deduction, phase_start))
        reduction_amount = max(0.0, qoc_gross - final_deduction)

        # DEDUCCIÓN REAL USABLE (el menor de los dos)
        deduction_real = min(qoc_gross, final_deduction)

        # ────────────────────────────────────────────────
        # RESULTADOS – PRESENTACIÓN CORREGIDA
        # ────────────────────────────────────────────────
        tab_data, tab_results = st.tabs([t["data_tab_title"], t["results_tab_title"]])

        with tab_data:
            st.subheader(t["data_subtitle"])
            data_summary = {
                "Concepto": t["data_concepts"],
                "Valor": [
                    filing_status,
                    format_money(total_income),
                    format_money(base_salary_est),
                    format_money(ot_total_shown),
                    format_money(payment_additional_1_5),
                    format_money(payment_additional_2_0),
                    method_used,
                    non_exempt,
                    over_40,
                    ot_1_5x
                ]
            }
            st.dataframe(pd.DataFrame(data_summary), width='stretch')

        with tab_results:
            st.subheader(t["results_title"])

            # Mensaje principal claro
            if qoc_gross <= final_deduction:
                st.success(t["deduction_real_no_limit"].format(format_money(deduction_real)))
            else:
                st.warning(t["deduction_real_with_limit"].format(format_money(deduction_real)))
                st.info(t["limit_info"].format(format_money(qoc_gross), format_money(final_deduction)))

            st.markdown("---")

            col_left_res, col_right_res = st.columns([1, 2])

            with col_left_res:
                st.metric(
                    label=t["deduction_real_label"],
                    value=format_money(deduction_real),
                    delta=t["deduction_real_delta"]
                )
                st.success(t["deduction_real_success"])

            with col_right_res:
                st.subheader(t["breakdown_subtitle"])
                st.metric(t["qoc_gross_label"], format_money(qoc_gross))
                st.metric(t["phaseout_limit_label"], format_money(final_deduction))
                if reduction_amount > 0:
                    st.metric(t["reduction_label"], f"-{format_money(reduction_amount)}")
                st.metric(t["final_after_limit_label"], format_money(deduction_real), delta_color="normal")

            st.markdown(t["chart_title"])
            chart_data = pd.DataFrame({
                "Categoría": t["chart_categories"],
                t["chart_money_column"]: [qoc_gross, final_deduction, deduction_real]
            })
            st.bar_chart(chart_data.set_index("Categoría"))

            st.caption(t["chart_caption"])

# Footer
st.markdown("---")
st.caption(t["footer"].format(date=datetime.now().strftime("%Y-%m-%d")))
