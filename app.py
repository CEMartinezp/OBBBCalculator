import streamlit as st
import pandas as pd
from datetime import datetime
from logic import calculate_ot_premium, apply_phaseout
from fpdf import FPDF
from PyPDF2 import PdfMerger
import tempfile
import os

# ────────────────────────────────────────────────
# CONFIGURACIÓN INICIAL
# ────────────────────────────────────────────────
if "eligible_override" not in st.session_state:
    st.session_state.eligible_override = False

if "results" not in st.session_state:
    st.session_state.results = None

if "show_results" not in st.session_state:
    st.session_state.show_results = False
    
st.set_page_config(
    page_title="ZaiOT",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def pretty_money_input(
    label: str,
    value: float = 0.0,
    step: float = 100.0,
    decimals: int = 2,
    key: str | None = None,
    help: str | None = None,
    lang: str = "es",          # <-- we pass the language here
    currency: str = "$"
) -> float:
    """
    number_input + language-aware pretty preview with correct separators
    """
    cols = st.columns([1.5, 3])  # or [7, 3], [5, 2], etc. — adjust to taste

    with cols[0]:
        num = st.number_input(
            label,
            min_value=0.0,
            value=value,
            step=step,
            format=f"%.{decimals}f",
            key=key,
            help=help,
        )

    with cols[1]:
        if num == 0:
            st.metric(label=" ", value=f"{currency}0")
            return num

        # ────────────────────────────────────────────────
        # Language-aware formatting
        # ────────────────────────────────────────────────
        if lang == "es":
            # Spanish/LatAm style: dot = thousands, comma = decimal
            # 1234567.89 → "1.234.567,89"
            formatted = f"{num:,.{decimals}f}"          # first get US style
            formatted = formatted.replace(",", "X")      # temp replace
            formatted = formatted.replace(".", ",")      # dot → comma (decimal)
            formatted = formatted.replace("X", ".")      # comma → dot (thousands)
        else:
            # Default / en-US: comma = thousands, dot = decimal
            formatted = f"{num:,.{decimals}f}"

        display_value = f"{currency}{formatted}"
        
        st.metric(
            label=" ", 
            value= display_value,
        )

    return num

def format_money(value):
    if value is None or value <= 0:
        return "$0"
    formatted = f"{int(value):,}"
    formatted = formatted.replace(",", ".")
    return f"${formatted}"

# ────────────────────────────────────────────────
# TEXTOS COMPLETOS – DICCIONARIO 100% COMPLETO Y ACTUALIZADO
# ────────────────────────────────────────────────
texts = {
    "es": {
        "title": "Calculadora de Deducción por Horas Extras (Ley OBBB 2025)",
        "desc": "Cálculo de la deducción anual máxima de las horas extras calificadas (hasta $12,500 para individual  o $25,000 Casado presentando declaración  conjunta).",
        "step1_title": "Paso 1: ¿Cumples con los requisitos básicos? (obligatorio)",
        "married_separated_label": "¿Eres casado presentando declaración por separado?",
        "over_40_label": "¿Te pagan horas extras por trabajar más de 40 horas a la semana?",
        "ss_check_label": "¿Tienes un Social Security valido?",
        "work_authorization_check_label": "¿Tienes un permiso de trabajo valido?",
        "ot_1_5x_label": "¿La mayoría de tus horas extras se pagan a medio tiempo (1.5x tu tarifa normal)?",
        "unlock_message": "Según tus respuestas, es posible que no califiques automáticamente para la deducción. Consulta con un contador antes de usar esta calculadora. Si aun deseas proseguir, haz click abajo para confirmar que calificas de todos modos",
        "override_button": "Sí califico y quiero continuar de todos modos",
        "override_success": "¡Genial! Has confirmado manualmente que calificas.",
        "eligible_blocked_info": "**Las respuestas de elegibilidad están bloqueadas.** Si necesitas cambiarlas, usa el botón de abajo.",
        "eligible_auto_success": "¡Excelente! Cumples los requisitos automáticamente.",
        "reiniciar_button": "🔄 Reiniciar respuestas de elegibilidad",
        "step2_title": "Paso 2: Ingresa tus datos de ingresos y horas extras",
        "magi_label": "Tu ingreso total aproximado del año (incluye horas extras, bonos, etc.) (\\$)",
        "filing_label": "Estado civil al presentar impuestos",
        "filing_options": ["Soltero", "Cabeza de Familia", "Casado presentando declaración conjunta"],
        "calc_button": "Calcular mi deducción estimada",
        "results_title": "Tus resultados estimados",
        "footer": "Actualizado en {date} \n Esta es solo una estimación – Consulta siempre a un profesional de impuestos",
        "answer_options": ["Sí", "No", "No estoy seguro"],

        # Ejemplo y pasos
        "example_title": "**Ejemplo:**",
        "example_text": """
        - Tu tarifa normal: **\\$25 por hora**  
        - Trabajas **10 horas extras** a 1.5x → te pagan **\\$375 total** (\\$250 de base + **\\$125 de dinero extra**)  
        - **Opción A**: Escribe **\\$375** y elige "Todo junto"  
        - **Opción B**: Escribe tarifa **\\$25**f¿Tu trabajo es de tipo 'no exento' de horas extras? (non-exempt) y 10 horas a 1.5x
        """,
        "step3_title": "Paso 3: Elige cómo ingresar tus datos de horas extras",
        "step3_info": "**Puedes usar una de estas dos formas**:\n"
                      "- **Opción A – Más rápida** (por monto total recibido):\n"  
                      "  Úsala si solo tienes el importe total que te pagaron por horas extras (en tus recibos o W-2).\n"
                      "  Es más simple, pero menos precisa si hubo pagos a doble tiempo o tarifas diferentes.\n"
                      "\n"
                      "- **Opción B – Más precisa** (por horas trabajadas):\n"
                      "  Úsala si tienes registro de las horas extras trabajadas y tu tarifa horaria normal.\n"  
                      "  Es la forma más exacta, especialmente si tuviste horas a 1.5x y a 2.0x.",
                      
        # Opción A
        "option_a_title": "**Opción A** (por monto total pagado)",
        "ot_total_1_5_paid_label": "Monto TOTAL que te pagaron por horas extras este año a medio tiempo (\\$)",
        "ot_total_1_5_paid_help": "Revisa tus recibos de pago o W-2. Suma **todo** lo recibido por trabajar horas extras a medio tiempo.",
        "ot_total_2_0_paid_label": "Monto TOTAL que te pagaron por horas extras este año a doble tiempo (\\$)",
        "ot_total_2_0_paid_help": "Revisa tus recibos de pago o W-2. Suma **todo** lo recibido por trabajar horas extras a doble tiempo.",
        "ot_multiplier_options": ["1.5x (medio tiempo)", "2.0x (doble tiempo)"],
        "amount_included_label": "El monto que escribiste por horas extras, ¿incluye...?",
        "amount_included_options": [
            "Todo lo que recibí (base + hora extra)",
            "Solo el dinero extra adicional (el pago por ser horas extras)"
        ],
        "amount_included_help": "Especifica si descontaste el pago base en el monto que colocaste.",

        # Opción B
        "option_b_title": "**Opción B** (por horas trabajadas)",
        "regular_rate_label": "Tu tarifa horaria normal (\\$ por hora)",
        "regular_rate_help": "¿Cuánto te pagan normalmente por una hora, sin extras?",
        "ot_hours_1_5_label": "Horas totales en el año pagadas a medio tiempo (1.5x) (numero de horas)",
        "ot_hours_1_5_help": "Suma de **todas** las horas extras que te pagaron a 1.5 veces durante el año.",
        "dt_hours_2_0_label": "Horas totales en el año pagadas a doble tiempo (2.0x) (numero de horas)",
        "dt_hours_2_0_help": "Horas pagadas al doble (ej: fines de semana o turnos especiales).",

        # Mensajes de ayuda FLSA
        "flsa_married_separated_help": "Si estas casado pero estas presentando la declaración por separado.",
        "flsa_over_40_help": "¿Te pagan más cuando superas las 40 horas por semana? Eso es la regla principal.",
        "flsa_ot_1_5x_help": "¿Casi todo tu pago extra es 1.5 veces tu tarifa normal? (ej: \\$30 en vez de \\$20). Si es doble en algunos días, igual puede contar.",
        "flsa_ss_check_help": "Si no tienes un Social Security valido no puedes calificar para la dedducion.",
        "flsa_work_authorization_check_help": "¿Tienes autorización legal para trabajar en EE.UU. (ej: ciudadanía, green card, visa de trabajo, etc.)?",

        # Errores y métodos
        "error_no_data": "⚠️ Completa al menos una de las opciones del **Paso 3** para calcular.",
        "error_empty_option_a": "⚠️ Opción A está incompleta. Completa al menos una de las opciones para calcular",
        "error_empty_option_b": "⚠️ Opción b está incompleta. Completa al menos una de las opciones para calcular",
        "error_missing_total_income": "⚠️ Paso 2 está incompleto. Debes introducir tu ingreso total aproximado del año para continuar.",
        "error_option_a_b": "Completaste ambas opciones, pero los resultados **no coinciden**.\n\n"
                            "Opción A → Pago adicional estimado: \\{}\n\n"
                            "Opción B → Pago adicional estimado: \\{}",
        "warning_option_a_b": "Revisa y corrige los valores para continuar.",
        "method_hours": "Por horas trabajadas (Opción B)",
        "method_total_combined": "Por monto total (Opción A - todo junto)",
        "method_total_premium": "Por monto total (Opción A - solo dinero extra)",
        "method_a_and_b": "Opción A y Opción B",

        # Resumen de datos
        "data_tab_title": "Resumen de tus datos",
        "data_subtitle": "Basado en lo que ingresaste",
        "data_concepts": [
            "Estado civil al declarar impuestos",
            "Ingreso total aproximado del año (base + extras)",
            "Salario base estimado (ingeso total sin extras)",
            "Total pagado por horas extras a medio tiempo (base + extra)",
            "Total pagado por horas extras a doble tiempo (base + extra)",
            "Total pagado por horas extras (base + extras)",
            "Pago adicional 1.5x (deducible)",
            "Pago adicional 2.0x (deducible)",
            "Método usado",
            "¿Le pagan horas extras por trabajar mas de 40h/semana?",
            "¿Principalmente 1.5x?",
            "¿Esta casado presentando declaracion por separado?",
            "¿Tiene un Social Security válido?",
            "¿Tienes un permiso de trabajo válido?"
        ],

        # Resultados
        "results_tab_title": "Resultados y deducción",
        "total_deduction_label": "Deducción que vas a usar en la linea 14 del schedule 1a",
        "total_deduction_delta": "Este es el monto final a restar de tus impuestos",
        "total_deduction_success": "Esta es la cantidad que puedes usar para linea 14 del schedule 1a. 💰",
        "total_deduction_no_limit": "**Puedes deducir {}** por el dinero adicional que ganaste en horas extras.",
        "total_deduction_with_limit": "**Puedes deducir {}** por horas extras (limitado por tu ingreso total).",
        "limit_info": "Tu pago adicional por overtime fue de {}, pero según tu ingreso total el máximo que puedes deducir es {}. Por eso se reduce a esta cantidad.",
        "breakdown_subtitle": "Desglose detallado",
        "qoc_gross_label": "Monto total ganado por horas extras",
        "phaseout_limit_label": "Límite máximo deducible permitido por tu ingreso total",
        "reduction_label": "Reducción aplicada",
        "final_after_limit_label": "**Deducción final después de comparar tu deducción con el maximo permitido**",

        # Descarga PDF
        "download_section_title": "Descargar Reporte en PDF",
        "download_name_label": "Tu nombre completo (aparecerá en el reporte)",
        "download_name_placeholder": "Ej: Juan Pérez",
        "download_w2_label": "¿Cuántos formularios W-2 o paystubs usaste para estos cálculos?",
        "download_w2_options": ["1", "2", "3 o más"],
        "download_docs_label": "Sube tus dofcumentos (W-2, paystubs, etc.) como evidencia (opcional, pero recomendado)",
        "download_docs_help": "Puedes subir uno o varios PDFs. Se agregarán al final del reporte.",
        "download_button": "Generar y Descargar Reporte PDF",
        "download_error_name": "Por favor, ingresa tu nombre para generar el reporte.",
        "pdf_title": "Reporte de Deducción por Horas Extras - Ley OBBB 2025",
        "pdf_generated_by": "Generado por ZaiOT",
        "pdf_date": "Fecha de generación: {}",
        "pdf_user_name": "Nombre del contribuyente: {}",
        "pdf_used_count": "Número de documentos utilizados: {}",
        "pdf_summary_title": "Resumen de Datos Ingresados",
        "pdf_results_title": "Resultados y Deducción Estimada",
        "pdf_evidence_title": "Documentos Adjuntos como Evidencia",
        "pdf_no_docs": "No se subieron documentos de evidencia.",
        
        # Disclaimer
        "disclaimer_label": "DESCARGO DE RESPONSABILIDAD",
        "disclaimer": "**Disclaimer:** Esta herramienta es solo para estimaciones informativas. No sustituye asesoría profesional de impuestos.\n"  
                      "Consulta a un contador certificado antes de usar cualquier deducción en tu declaración fiscal.",
        "disclaimer_msg": "IMPORTANTE: Esta calculadora genera SOLO ESTIMACIONES APROXIMADAS de la deducción por horas extras según la Ley OBBB 2025."
                          "NO es asesoría fiscal, legal ni contable. Los resultados pueden variar y NO garantizan aceptación por el IRS."
                          "Siempre consulta a un contador o profesional de impuestos certificado antes de usar cualquier deducción en tu declaración."
                          "Uso de esta herramienta es bajo tu propia responsabilidad.",
        
        # Theme colors:
        "theme_modes": ["Modo Claro", "Modo Oscuro"]
    }
}

# Idioma
col_idioma, col_tema = st.columns([1, 1])  # o [2,1] si quieres más espacio para idioma

language = st.selectbox(
    "🌐 Idioma",
    ["Español"],
    index=0,
    label_visibility="visible"
)
if language == "Español":
    st.session_state.language = "es"
else:
    st.session_state.language = "en"
    
t = texts[st.session_state.language]

# ────────────────────────────────────────────────
# ────────────────────────────────────────────────
st.title(t["title"])

st.markdown(
    f"""
    <div style="
        font-size: 1.3rem;
        line-height: 1.6;
        padding: 16px;
        background-color: var(--secondary-background-color);
        border-left: 6px solid #2196F3;
        border-radius: 4px;
        color: var(--text-color);
    ">
    {t["desc"]}
    </div>
    """,
    unsafe_allow_html=True
)

st.warning(t["disclaimer"])

# ────────────────────────────────────────────────
# ELEGIBILIDAD FLSA
# ────────────────────────────────────────────────
eligible = st.session_state.eligible_override

with st.expander(f"### {t['step1_title']}", expanded=not eligible):
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
    civil_married_separated = st.radio(
        t["married_separated_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["flsa_married_separated_help"]
    )
    ss_check = st.radio(
        t["ss_check_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["flsa_ss_check_help"]
    )
    work_authorization_check = st.radio(
        t["work_authorization_check_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["flsa_work_authorization_check_help"]
    )

    auto_eligible = (
                     civil_married_separated == t["answer_options"][1] and 
                     over_40 == t["answer_options"][0] and 
                     ot_1_5x == t["answer_options"][0] and
                     ss_check == t["answer_options"][0] and
                     work_authorization_check == t["answer_options"][0]
                     )

    eligible = auto_eligible or st.session_state.eligible_override

    if eligible:
        if st.session_state.eligible_override:
            st.info(t["eligible_blocked_info"])
        else:
            # Elegible auto success
            st.session_state.eligible_override = True
            st.rerun()
        
        if st.button(t["reiniciar_button"], type="secondary", width='stretch'):
            st.session_state.eligible_override = False
            st.rerun()
    else:
        st.warning(t["unlock_message"])
        if st.button(t["override_button"], width='stretch'):
            st.session_state.eligible_override = True
            st.rerun()

# ────────────────────────────────────────────────
# SECCIÓN DE INGRESOS Y CÁLCULO
# ────────────────────────────────────────────────
if eligible:
    with st.expander(f"### {t['step2_title']}", expanded=True):
        filing_status = st.selectbox(t["filing_label"], t["filing_options"])
        total_income = pretty_money_input(
            t["magi_label"],
            value=0.0,
            step=1000.0,
            decimals=2,          
            help=None,
            lang=st.session_state.language
        )
    with st.expander(f"### {t['step3_title']}", expanded=True):
        st.info(t["step3_info"])
        with st.expander(t["example_title"], expanded=False):
            st.markdown(t["example_text"])
        
        # Expanders para cada opción
        with st.expander(t["option_a_title"], expanded=False):
            ot_1_5_total = pretty_money_input(
                t["ot_total_1_5_paid_label"],
                value=0.0,
                step=100.0,
                decimals=2,
                help=t["ot_total_1_5_paid_help"],
                lang=st.session_state.language
            )
            ot_2_0_total = pretty_money_input(
                t["ot_total_2_0_paid_label"],
                value=0.0,
                step=100.0,
                decimals=2,
                help=t["ot_total_2_0_paid_help"],
                lang=st.session_state.language
            )
            amount_included = st.radio(
                t["amount_included_label"],
                t["amount_included_options"],
                horizontal=True,
                key="type_total",
                help=t["amount_included_help"],
            )
            is_total_combined = "todo" in amount_included.lower()

        with st.expander(t["option_b_title"], expanded=False):
            regular_rate = pretty_money_input(
                t["regular_rate_label"],
                value=0.0,
                step=0.5,
                decimals=2,
                help=t["regular_rate_help"]
            )
            ot_hours_1_5 = pretty_money_input(
                t["ot_hours_1_5_label"],
                value=0.0,
                step=5.0,
                help=t["ot_hours_1_5_help"],
                decimals=2,
                lang=st.session_state.language,
                currency=" "
            )
            dt_hours_2_0 = pretty_money_input(
                t["dt_hours_2_0_label"],
                value=0.0,
                step=5.0,
                decimals=2,
                help=t["dt_hours_2_0_help"],
                lang=st.session_state.language,
                currency=" "
            )
            
    # ────────────────────────────────────────────────
    # Boton de Calcular
    # ────────────────────────────────────────────────
    if st.button(t["calc_button"], type="primary", width='stretch'):
        if "calc_error" in st.session_state:
            del st.session_state.calc_error

        # ────────────────────────────────────────────────
        # Validaciones previas (ya las tienes, las mantengo iguales)
        # ────────────────────────────────────────────────
        incomplete_step2 = total_income <= 0
        # Opción A
        a_has_1_5 = ot_1_5_total > 0
        a_has_2_0 = ot_2_0_total > 0
        a_complete = a_has_1_5 or a_has_2_0
        a_partial = (a_has_1_5 != a_has_2_0)  # uno sí, otro no
        # Opción B
        b_has_rate = regular_rate > 0
        b_has_hours = (ot_hours_1_5 + dt_hours_2_0) > 0
        b_complete = b_has_rate and b_has_hours
        b_partial = (b_has_rate != b_has_hours)  # uno sí, otro no
        
        # Detectar error específico (solo uno por vez)
        error_msg = None
        if incomplete_step2:
            error_msg = t["error_missing_total_income"]         
        elif not a_complete and not b_complete:
            error_msg = t["error_no_data"]
        elif not a_partial and not b_complete and not a_complete:
            error_msg = t["error_empty_option_a"]
        elif b_partial and not a_complete and not b_complete:
            error_msg = t["error_empty_option_b"]
        elif b_partial and a_complete:
            error_msg = "Has intentado completar ambas opciones, pero aún falta completar la Opción B. Para continuar, por favor finaliza o elimina la información ingresada en la Opción B."

        if error_msg:
            st.session_state.calc_error = error_msg
            st.error(error_msg)
        else:
            # ────────────────────────────────────────────────
            # Calcular siempre lo que se pueda
            # ────────────────────────────────────────────────
            method_used = None
            qoc_gross = 0.0
            ot_total_paid = 0.0
            ot_1_5_premium = 0.0
            ot_2_0_premium = 0.0

            # Opción B (prioridad si está completa)
            if b_complete:
                ot_1_5_total_b = ot_hours_1_5 * regular_rate * 1.5
                ot_2_0_total_b = dt_hours_2_0 * regular_rate * 2.0
                ot_total_paid_b = ot_1_5_total_b + ot_2_0_total_b
                ot_1_5_premium_b = calculate_ot_premium(ot_1_5_total_b, 1.5, "total")
                ot_2_0_premium_b = calculate_ot_premium(ot_2_0_total_b, 2.0, "total")
                qoc_gross_b = ot_1_5_premium_b + ot_2_0_premium_b

            # Opción A
            if a_complete:
                ot_total_paid_a = ot_1_5_total + ot_2_0_total
                amount_type = "total" if is_total_combined else "premium"
                ot_1_5_premium_a = calculate_ot_premium(ot_1_5_total, 1.5, amount_type)
                ot_2_0_premium_a = calculate_ot_premium(ot_2_0_total, 2.0, amount_type)
                qoc_gross_a = ot_1_5_premium_a + ot_2_0_premium_a

            # ────────────────────────────────────────────────
            # Decidir qué usar
            # ────────────────────────────────────────────────
            if b_complete and a_complete:
                # Comparar con tolerancia razonable (ej: diferencia < $1 o < 0.1%)
                diff_total = abs(ot_total_paid_b - ot_total_paid_a)
                diff_premium = abs(qoc_gross_b - qoc_gross_a)
                tolerance = 1.0  # o 0.001 * ot_total_paid_b si prefieres %

                if diff_total <= tolerance and diff_premium <= tolerance:
                    # Coinciden → preferimos Opción B (más precisa)
                    method_used = t["method_hours"] + " (validado con Opción A)"
                    qoc_gross = qoc_gross_b
                    ot_total_paid = ot_total_paid_b
                    ot_1_5_premium = ot_1_5_premium_b
                    ot_2_0_premium = ot_2_0_premium_b
                else:
                    st.session_state.calc_error = error_msg
                    st.error(t["error_option_a_b"].format(format_money(qoc_gross_a), format_money(qoc_gross_b))) 
                    st.warning(t["warning_option_a_b"])                   
                    st.stop()  # ← importante: no continuar si hay inconsistencia

            elif b_complete:
                method_used = t["method_hours"]
                qoc_gross = qoc_gross_b
                ot_total_paid = ot_total_paid_b
                ot_1_5_premium = ot_1_5_premium_b
                ot_2_0_premium = ot_2_0_premium_b

            elif a_complete:
                method_used = t["method_total_combined"] if is_total_combined else t["method_total_premium"]
                qoc_gross = qoc_gross_a
                ot_total_paid = ot_total_paid_a
                ot_1_5_premium = ot_1_5_premium_a
                ot_2_0_premium = ot_2_0_premium_a

            # ────────────────────────────────────────────────
            # Continuar con el cálculo final
            # ────────────────────────────────────────────────
            if not error_msg:  # solo si no hubo inconsistencia
                base_salary_est = total_income - qoc_gross

                is_joint = filing_status == t["filing_options"][2]
                max_deduction = 25000 if is_joint else 12500
                phase_start = 300000 if is_joint else 150000
                deduction_limit = max(0.0, apply_phaseout(total_income, max_deduction, phase_start))
                total_deduction = min(qoc_gross, deduction_limit)

                # Guardar resultados
                st.session_state.results = {
                    "filing_status": filing_status,
                    "total_income": total_income,
                    "base_salary_est": base_salary_est,
                    "ot_total_paid": ot_total_paid,
                    "ot_1_5_total": ot_hours_1_5 * regular_rate * 1.5 if b_complete else ot_1_5_total,
                    "ot_2_0_total": dt_hours_2_0 * regular_rate * 2 if b_complete else ot_2_0_total,
                    "ot_1_5_premium": ot_1_5_premium,
                    "ot_2_0_premium": ot_2_0_premium,
                    "method_used": method_used,
                    "civil_married_separated": civil_married_separated,
                    "over_40": over_40,
                    "ot_1_5x": ot_1_5x,
                    "ss_check": ss_check,
                    "work_authorization_check": work_authorization_check,
                    "qoc_gross": qoc_gross,
                    "deduction_limit": deduction_limit,
                    "total_deduction": total_deduction
                }
                st.session_state.show_results = True
                st.rerun()
        
# ────────────────────────────────────────────────
# MOSTRAR RESULTADOS (persiste siempre después de calcular)
# ────────────────────────────────────────────────
if eligible and st.session_state.show_results:
    tab_results, tab_data = st.tabs([t["results_tab_title"], t["data_tab_title"]])

    with tab_results:
        st.subheader(t["results_title"])

        data = st.session_state.results
        qoc_gross = data["qoc_gross"]
        deduction_limit = data["deduction_limit"]
        total_deduction = data["total_deduction"]

        if qoc_gross <= deduction_limit:
            st.success(t["total_deduction_no_limit"].format(format_money(total_deduction)))
        else:
            st.warning(t["total_deduction_with_limit"].format(format_money(total_deduction)))
            st.info(t["limit_info"].format(f'\\{format_money(qoc_gross)}', f'\\{format_money(deduction_limit)}'))

        st.markdown("---")

        col_left_res, col_right_res = st.columns([1, 2])

        with col_left_res:
            st.metric(
                label=t["total_deduction_label"],
                value=format_money(total_deduction),
                delta=t["total_deduction_delta"]
            )
            st.success(t["total_deduction_success"])

        with col_right_res:
            st.subheader(t["breakdown_subtitle"])
            st.metric(t["qoc_gross_label"], format_money(qoc_gross))
            st.metric(t["phaseout_limit_label"], format_money(deduction_limit))
            st.metric(t["final_after_limit_label"], format_money(total_deduction), delta_color="normal")
    
    with tab_data:
        st.subheader(t["data_subtitle"])
        data = st.session_state.results
        data_summary = {
            "Concepto": t["data_concepts"],
            "Valor": [
                data["filing_status"],
                format_money(data["total_income"]),
                format_money(data["base_salary_est"]),
                format_money(data["ot_1_5_total"]),
                format_money(data["ot_2_0_total"]),
                format_money(data["ot_total_paid"]),
                format_money(data["ot_1_5_premium"]),
                format_money(data["ot_2_0_premium"]),
                data["method_used"],
                data["over_40"],
                data["ot_1_5x"],
                data["civil_married_separated"],
                data["ss_check"],
                data["work_authorization_check"]
            ]
        }
        st.dataframe(pd.DataFrame(data_summary), width='stretch')

# ────────────────────────────────────────────────
# DESCARGA DE REPORTE PDF
# ────────────────────────────────────────────────
if eligible and st.session_state.results:
    st.subheader(t["download_section_title"])

    user_name = st.text_input(t["download_name_label"], placeholder=t["download_name_placeholder"])
    uploaded_files = st.file_uploader(
        t["download_docs_label"],
        type=["pdf"],
        accept_multiple_files=True,
        help=t["download_docs_help"]
    )
    # Número de documentos cargados
    num_docs = len(uploaded_files) if uploaded_files is not None else 0

    if st.button(t["download_button"], type="primary", width='stretch'):
        if not user_name.strip():
            st.error(t["download_error_name"])
        else:
            with st.spinner("Generando reporte PDF..."):
                # Crear PDF principal
                pdf = FPDF()
                pdf.add_page()
                
                # ── Página 1: SOLO el disclaimer ────────────────────────────────
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 15, t["disclaimer_label"], ln=True, align="C")
                pdf.ln(8)
                pdf.set_font("Arial", "B", 11)
                pdf.multi_cell(0, 7, t["disclaimer_msg"], align="J")
                # Forzamos nueva página para el contenido real
                pdf.add_page() 
                
                # ── A partir de aquí va el contenido normal ──────────────────────
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, t["pdf_title"], ln=True, align="C")
                pdf.set_font("Arial", "", 12)
                pdf.cell(0, 10, t["pdf_generated_by"], ln=True, align="C")
                pdf.cell(0, 10, t["pdf_date"].format(datetime.now().strftime("%Y-%m-%d %H:%M")), ln=True, align="C")
                pdf.ln(8)
                
                # User name, document count, summary, etc.
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, t["pdf_user_name"].format(user_name), ln=True)
                pdf.cell(0, 10, t["pdf_used_count"].format(num_docs), ln=True)
                pdf.ln(8)

                # Resumen
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, t["pdf_summary_title"], ln=True)
                pdf.set_font("Arial", "", 10)

                data = st.session_state.results
                summary_lines = [
                    f"{t['data_concepts'][0]}: {data['filing_status']}",
                    f"{t['data_concepts'][1]}: {format_money(data['total_income'])}",
                    f"{t['data_concepts'][2]}: {format_money(data['base_salary_est'])}",
                    f"{t['data_concepts'][3]}: {format_money(data['ot_1_5_total'])}",
                    f"{t['data_concepts'][4]}: {format_money(data['ot_2_0_total'])}",
                    f"{t['data_concepts'][5]}: {format_money(data['ot_total_paid'])}",
                    f"{t['data_concepts'][6]}: {format_money(data['ot_1_5_premium'])}",
                    f"{t['data_concepts'][7]}: {format_money(data['ot_2_0_premium'])}",
                    f"{t['data_concepts'][8]}: {data['method_used']}",
                    f"{t['data_concepts'][9]}: {data['over_40']}",
                    f"{t['data_concepts'][10]}: {data['ot_1_5x']}",
                    f"{t['data_concepts'][11]}: {data['civil_married_separated']}",
                    f"{t['data_concepts'][12]}: {data['ss_check']}",
                    f"{t['data_concepts'][13]}: {data['work_authorization_check']}"
                ]
                
                for line in summary_lines:
                    pdf.multi_cell(0, 8, line)

                pdf.ln(8)

                # Resultados
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, t["pdf_results_title"], ln=True)
                pdf.set_font("Arial", "", 10)
                pdf.multi_cell(0, 8, f"{t['total_deduction_label']}: {format_money(data['total_deduction'])}")
                pdf.multi_cell(0, 8, f"{t['qoc_gross_label']}: {format_money(data['qoc_gross'])}")
                pdf.multi_cell(0, 8, f"{t['phaseout_limit_label']}: {format_money(data['deduction_limit'])}")
                pdf.ln(8)

                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, t["pdf_evidence_title"], ln=True)
                pdf.set_font("Arial", "", 10)
                if uploaded_files:
                    pdf.multi_cell(0, 8, f"Se adjuntan {len(uploaded_files)} documento(s) como evidencia.")
                else:
                    pdf.multi_cell(0, 8, t["pdf_no_docs"])

                # Guardar PDF principal de forma segura (sin mkstemp)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_main:
                    pdf.output(tmp_main.name)
                    main_pdf_path = tmp_main.name

                # Cerrar explícitamente
                tmp_main.close()

                # Combinar PDFs
                merger = PdfMerger()
                merger.append(main_pdf_path)

                temp_upload_paths = []
                if uploaded_files:
                    for uploaded_file in uploaded_files:
                        tmp_path = tempfile.mktemp(suffix=".pdf")  # mktemp sigue siendo seguro aquí
                        with open(tmp_path, "wb") as tmp_upload:
                            tmp_upload.write(uploaded_file.read())
                        merger.append(tmp_path)
                        temp_upload_paths.append(tmp_path)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_final:
                    merger.write(tmp_final.name)
                    final_pdf_path = tmp_final.name

                merger.close()
                tmp_final.close()

                # Limpieza
                os.unlink(main_pdf_path)
                for path in temp_upload_paths:
                    try:
                        os.unlink(path)
                    except PermissionError:
                        pass

                # Descarga
                with open(final_pdf_path, "rb") as f:
                    st.download_button(
                        label="Descargar Reporte PDF Ahora",
                        data=f,
                        file_name=f"Reporte_Deduccion_Horas_Extras_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        key="download_pdf"
                    )

                try:
                    os.unlink(final_pdf_path)
                except PermissionError:
                    pass

# Footer
st.markdown("---")
st.caption(t["footer"].format(date=datetime.now().strftime("%Y-%m-%d")))