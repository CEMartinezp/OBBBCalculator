import streamlit as st
import pandas as pd
from datetime import datetime
from logic import calculate_ot_premium, apply_phaseout
from fpdf import FPDF
from PyPDF2 import PdfMerger
from io import BytesIO

# ────────────────────────────────────────────────
# CONFIGURACIÓN INICIAL
# ────────────────────────────────────────────────
if "eligible_override" not in st.session_state:
    st.session_state.eligible_override = False

if "results" not in st.session_state:
    st.session_state.results = None

if "show_results" not in st.session_state:
    st.session_state.show_results = False
    
if "pdf_generated" not in st.session_state:   
    st.session_state.pdf_generated = False
    
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
    cols = st.columns([1.5, 3])  # or [7, 3], [5, 2], etc. -- adjust to taste

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

def format_number(value: float, lang:str="es", currency="$", decimals=2) -> str:
    if value is None or value <= 0:
        return f"{currency}0"
    
    if lang == "es":
            # Spanish/LatAm style: dot = thousands, comma = decimal
            # 1234567.89 → "1.234.567,89"
            formatted = f"{value:,.{decimals}f}"          # first get US style
            formatted = formatted.replace(",", "X")      # temp replace
            formatted = formatted.replace(".", ",")      # dot → comma (decimal)
            formatted = formatted.replace("X", ".")      # comma → dot (thousands)
    else:
        # Default / en-US: comma = thousands, dot = decimal
        formatted = f"{value:,.{decimals}f}"

    return f"{currency}{formatted}"

def safe_line(txt):
    # If line is too long without spaces, force break every 30 chars or so
    if len(txt) > 60 and ' ' not in txt:
        return '\n'.join(txt[i:i+50] for i in range(0, len(txt), 50))
    return txt

# ────────────────────────────────────────────────
# TEXTOS COMPLETOS – DICCIONARIO 100% COMPLETO Y ACTUALIZADO
# ────────────────────────────────────────────────
texts = {
    "es": {
        "title": "Calculadora de Deducción por Horas Extras (Ley OBBB 2025)",
        "desc": "Cálculo de la deducción anual máxima de las horas extras calificadas (hasta $12,500 para individual  o $25,000 Casado presentando declaración  conjunta).",
        "step1_title": "Paso 1: ¿Cumples con los requisitos básicos? (obligatorio)",
        "over_40_label": "¿Te pagan horas extras por trabajar más de 40 horas a la semana?",
        "ss_check_label": "¿Tiene un SSN válido para trabajar?",
        "itin_check_label": "¿Tiene ITIN?",
        "ot_1_5x_label": "¿La mayoría de tus horas extras se pagan a medio tiempo (1.5x la tarifa normal)?",
        "unlock_message": "Según tus respuestas, es posible que no califiques para la deducción. Consulta con un contador antes de usar esta calculadora. Si aun deseas proseguir, haz click abajo para confirmar que calificas de todos modos",
        "override_button": "Sí califico y quiero continuar de todos modos",
        "override_success": "¡Genial! Has confirmado manualmente que calificas.",
        "eligible_blocked_info": "**Las respuestas de elegibilidad están bloqueadas.** Si necesitas cambiarlas, usa el botón de abajo.",
        "eligible_auto_success": "¡Excelente! Cumples los requisitos automáticamente.",
        "reiniciar_button": "🔄 Reiniciar respuestas de elegibilidad",
        "step2_title": "Paso 2: Ingresa tus datos de ingresos y horas extras",
        "magi_label": "Ingreso total aproximado del año (incluye horas extras, bonos, etc.) (\\$)",
        "filing_status_label": "Estado civil al presentar impuestos",
        "filing_status_options": ["Soltero", "Cabeza de Familia", "Casado presentando declaración conjunta", "Casado presentando declaración Separada"],
        "calc_button": "Calcular mi deducción estimada",
        "results_title": "Tus resultados estimados",
        "footer": "Actualizado en {date} \n Esta es solo una estimación – Consulta siempre a un profesional de impuestos",
        "answer_options": ["Sí", "No", "No estoy seguro"],

        # Ejemplo y pasos
        "example_title": "**Ejemplo:**",
        "example_text": """
            - **Tarifa normal:** \\$25 por hora  
            - Trabajas **10 horas extras** pagadas a **1.5x**  

            👉 Cálculo:
            - Pago total recibido por esas horas: **\\$375**  
            (\\$25 × 1.5 × 10 horas)  
            - De ese total:
            - **\\$250** corresponde al salario base (\\$25 × 10)
            - **\\$125** corresponde al pago adicional por horas extras (monto deducible)

            ---

            **Opción A (Más rápida):**  
            Escribe **\\$375** como monto total pagado por horas extras.

            **Opción B (Más precisa):**  
            Escribe:
            - Tarifa normal: **\\$25**
            - Horas a 1.5x: **10**
        """,
        "step3_title": "Paso 3: Elige cómo ingresar tus datos de horas extras",
        "step3_info": "**Puedes usar una de estas dos formas**:\n"
                      "- **Opción A – Más rápida** (por monto total recibido):\n"  
                      "  Úsala si solo tienes el importe total que te pagaron por horas extras (en tus recibos o W-2).\n"
                      "  Es más simple, pero menos precisa si hubo pagos a doble tiempo o tarifas diferentes, y no podrá mostrar el monto de cuanto ganas por hora por el tiempo extra.\n"
                      "\n"
                      "- **Opción B – Más precisa** (por horas trabajadas):\n"
                      "  Se usa si se tiene el registro de las horas extras trabajadas y la tarifa horaria normal.\n"  
                      "  Es la forma más exacta, especialmente si tuviste horas a 1.5x y a 2.0x.",
        "choose_method_label": "¿Cómo deseas ingresar tus horas extras?",
        "choose_method_options": [
            "Tengo el monto total pagado (más rápido)",
            "Tengo mis horas y tarifa (más preciso)"
        ],
                      
        # Opción A
        "option_a_title": "**Opción A** (por monto total pagado)",
        "ot_total_1_5_paid_label": "Monto TOTAL que te pagaron por horas extras este año a medio tiempo (\\$)",
        "ot_total_1_5_paid_help": "Revisa tus recibos de pago o W-2. Suma **todo** lo recibido por trabajar horas extras a medio tiempo.",
        "ot_total_2_0_paid_label": "Monto TOTAL que te pagaron por horas extras este año a doble tiempo (\\$)",
        "ot_total_2_0_paid_help": "Revisa tus recibos de pago o W-2. Suma **todo** lo recibido por trabajar horas extras a doble tiempo.",
        "ot_multiplier_options": ["1.5x (medio tiempo)", "2.0x (doble tiempo)"],

        # Opción B
        "option_b_title": "**Opción B** (por horas trabajadas)",
        "regular_rate_label": "Tarifa horaria normal (\\$ por hora)",
        "regular_rate_help": "¿Cuánto te pagan normalmente por una hora, sin extras?",
        "ot_hours_1_5_label": "Horas totales en el año pagadas a medio tiempo (1.5x) (número de horas)",
        "ot_hours_1_5_help": "Suma de **todas** las horas extras que te pagaron a 1.5 veces durante el año.",
        "dt_hours_2_0_label": "Horas totales en el año pagadas a doble tiempo (2.0x) (número de horas)",
        "dt_hours_2_0_help": "Horas pagadas al doble (ej: fines de semana o turnos especiales).",

        # Mensajes de ayuda FLSA
        "over_40_help": "¿Te pagan más cuando superas las 40 horas por semana? Eso es la regla principal.",
        "ot_1_5x_help": "¿Casi todo su pago extra es 1.5 veces su tarifa normal? (ej: \\$30 en vez de \\$20). Si es doble en algunos días, igual puede contar.",
        "ss_check_help": "Si no tienes un Social Security válido no puedes calificar para la deducción.",
        "itin_check_help": "Si tiene un ITIN no califica para la deducción.",

        # Errores y métodos
        "error_no_data": "⚠️ Completa al menos una de las opciones del **Paso 3** para calcular.",
        "error_empty_option_a": "⚠️ Opción A está incompleta. Completa al menos una de las opciones para calcular",
        "error_empty_option_b": "⚠️ Opción b está incompleta. Completa al menos una de las opciones para calcular",
        "error_missing_total_income": "⚠️ Paso 2 está incompleto. Debes introducir su ingreso total aproximado del año para continuar.",
        "error_partial_option_b_conflict": "Has intentado completar ambas opciones, pero aún falta completar la Opción B. Para continuar, por favor finaliza o elimina la información ingresada en la Opción B.",
        "error_income_less_than_ot": "Su ingreso total aproximado del año no puede ser menor que el total pagado por sus horas extras.",
        "error_option_a_b": "Completaste ambas opciones, pero los resultados **no coinciden**.\n\n"
                            "Opción A → Pago adicional estimado: \\{}\n\n"
                            "Opción B → Pago adicional estimado: \\{}",
        "warning_option_a_b": "Revisa y corrige los valores para continuar.",
        "method_hours": "Por horas trabajadas (Opción B)",
        "method_total": "Por monto total (Opción A)",
        "method_a_and_b": "Opción A y Opción B",
        

        # Resumen de datos
        "data_tab_title": "Resumen de tus datos",
        "data_subtitle": "Basado en lo que ingresaste",
        "data_concepts": [
            "Ingreso total aproximado del año (base + extras)",
            "Salario base estimado (ingreso total sin extras)",
            "Total pagado por horas extras a medio tiempo (base + extra)",
            "Total pagado por horas extras a doble tiempo (base + extra)",
            "Total pagado por horas extras",
            "Pago adicional 1.5x (deducible)",
            "Pago adicional 2.0x (deducible)",
            "Pago por hora por 1.5x",
            "Pago por hora por 2.0x",
            "Limite para la deduccion",
            "Método usado",
            "¿Le pagan horas extras por trabajar más de 40h/semana?",
            "¿Las horas extras son principalmente 1.5x?",
            "¿Estado civil al declarar impuestos?",
            "¿Tiene un Social Security válido para trabajar?",
            "¿Tiene ITIN?"
        ],

        # Resultados
        "data_column_concept": "Concepto",
        "data_column_value": "Valor",
        "results_tab_title": "Resultados y deducción",
        "total_deduction_label": "Deducción que vas a usar en la linea 14 del schedule 1a",
        "total_deduction_delta": "Este es el monto final a restar de los impuestos",
        "total_deduction_success": "Esta es la cantidad que puedes usar para linea 14 del schedule 1a. 💰",
        "total_deduction_no_limit": "**Puedes deducir {}** por el monto adicional que ganaste en horas extras.",
        "total_deduction_with_limit": "**Puedes deducir {}** por horas extras (limitado por el ingreso total).",
        "limit_info": "El pago adicional por overtime fue de {}, pero según el ingreso total, el máximo que se puede deducir es {}. Por eso se reduce a esta cantidad.",
        "breakdown_subtitle": "Desglose detallado",
        "qoc_gross_label": "Monto total ganado por horas extras",
        "phaseout_limit_label": "Límite máximo deducible permitido por el ingreso total",
        "reduction_label": "Reducción aplicada",
        "final_after_limit_label": "**Deducción final después de comparar la deducción con el máximo permitido**",

        # Descarga PDF
        "spinner_generating_pdf": "Generando reporte PDF...",
        "download_button_now": "Descargar Reporte PDF Ahora",
        "download_section_title": "Descargar Reporte en PDF",
        "download_name_label": "Nombre completo (aparecerá en el reporte)",
        "download_name_placeholder": "Ej: Juan Pérez",
        "download_w2_options": ["1", "2", "3 o más"],
        "download_docs_label": "Sube tus documentos (W-2, paystubs, etc.) como evidencia (opcional, pero recomendado)",
        "download_docs_help": "Puedes subir uno o varios PDFs. Se agregarán al final del reporte.",
        "download_button": "Generar y Descargar Reporte PDF",
        "download_error_name": "Por favor, ingrese su nombre para generar el reporte.",
        "pdf_title": "Reporte de Deducción por Horas Extras - Ley OBBB 2025",
        "pdf_generated_by": "Hecho con ZaiOT",
        "pdf_date": "Fecha: {}",
        "pdf_user_name": "Nombre del contribuyente: {}",
        "pdf_used_count": "Número de documentos utilizados: {}",
        "pdf_summary_title": "Resumen de Datos Ingresados",
        "pdf_results_title": "Resultados y Deducción Estimada",
        "pdf_evidence_title": "Documentos Adjuntos como Evidencia",
        "pdf_no_docs": "No se subieron documentos de evidencia.",
        "pdf_docs_attached": "Se adjuntan {} documento(s) como evidencia.",
        "pdf_final_deduction": "DEDUCCIÓN FINAL: {}",
        
        # Disclaimer
        "disclaimer_label": "DESCARGO DE RESPONSABILIDAD",
        "disclaimer": "**Disclaimer:** Esta herramienta es solo para estimaciones informativas. No sustituye asesoría profesional de impuestos.\n"  
                      "Consulte con un contador certificado antes de usar cualquier deducción en una declaración fiscal.",
        "disclaimer_msg": "IMPORTANTE: Esta calculadora genera SOLO ESTIMACIONES APROXIMADAS de la deducción por horas extras según la Ley OBBB 2025."
                          "NO es asesoría fiscal, legal ni contable. Los resultados pueden variar y NO garantizan aceptación por el IRS."
                          "Siempre consulte a un contador o profesional de impuestos certificado antes de usar cualquier deducción en una declaración."
                          "Uso de esta herramienta es bajo su propia responsabilidad.",
        
        # Language
        "language_label": "🌐 Idioma",
        "language_options": ["Español", "English"]
    }
}

# Idioma
col_idioma, col_tema = st.columns([1, 1])  # o [2,1] si quieres más espacio para idioma

if "language" not in st.session_state:
    st.session_state.language = "es"
    
t = texts[st.session_state.language]

language = st.selectbox(
    t["language_label"],
    t["language_options"],
    index=0,
    label_visibility="visible"
)
if language == "Español":
    st.session_state.language = "es"
else:
    st.session_state.language = "en"

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
    
    filing_status = st.radio(
        t["filing_status_label"],
        t["filing_status_options"],
        index=0,
        horizontal=True,
        disabled=eligible,
    )
    
    over_40 = st.radio(
        t["over_40_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["over_40_help"]
    )
    ot_1_5x = st.radio(
        t["ot_1_5x_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["ot_1_5x_help"]
    )
    ss_check = st.radio(
        t["ss_check_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["ss_check_help"]
    )
    itin_check = st.radio(
        t["itin_check_label"],
        t["answer_options"],
        index=2,
        horizontal=True,
        disabled=eligible,
        help=t["itin_check_help"]
    )

    auto_eligible = (
                     filing_status != t["filing_status_options"][3] and 
                     over_40 == t["answer_options"][0] and 
                     ot_1_5x == t["answer_options"][0] and
                     ss_check == t["answer_options"][0] and
                     itin_check == t["answer_options"][1]
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
            error_msg = t["error_partial_option_b_conflict"]
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
            rate_1_5 = None
            rate_2_0 = None

            # Opción B (prioridad si está completa)
            if b_complete:
                ot_1_5_total_b = ot_hours_1_5 * regular_rate * 1.5
                ot_2_0_total_b = dt_hours_2_0 * regular_rate * 2.0
                ot_total_paid_b = ot_1_5_total_b + ot_2_0_total_b
                ot_1_5_premium_b = calculate_ot_premium(ot_1_5_total_b, 1.5, "total")
                ot_2_0_premium_b = calculate_ot_premium(ot_2_0_total_b, 2.0, "total")
                qoc_gross_b = ot_1_5_premium_b + ot_2_0_premium_b
                rate_1_5 = regular_rate * 1.5
                rate_2_0 = regular_rate * 2.0

            # Opción A
            if a_complete:
                ot_total_paid_a = ot_1_5_total + ot_2_0_total
                ot_1_5_premium_a = calculate_ot_premium(ot_1_5_total, 1.5, "total")
                ot_2_0_premium_a = calculate_ot_premium(ot_2_0_total, 2.0, "total")
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
                    st.error(t["error_option_a_b"].format(format_number(qoc_gross_a), format_number(qoc_gross_b))) 
                    st.warning(t["warning_option_a_b"])                   

            elif b_complete:
                method_used = t["method_hours"]
                qoc_gross = qoc_gross_b
                ot_total_paid = ot_total_paid_b
                ot_1_5_premium = ot_1_5_premium_b
                ot_2_0_premium = ot_2_0_premium_b

            elif a_complete:
                method_used = t["method_total"]
                qoc_gross = qoc_gross_a
                ot_total_paid = ot_total_paid_a
                ot_1_5_premium = ot_1_5_premium_a
                ot_2_0_premium = ot_2_0_premium_a

            # ────────────────────────────────────────────────
            # Continuar con el cálculo final
            # ────────────────────────────────────────────────
            if not error_msg:  # solo si no hubo inconsistencia
                base_salary_est = total_income - ot_total_paid
                is_joint = filing_status == t["filing_status_options"][2]
                max_deduction = 25000 if is_joint else 12500
                phase_start = 300000 if is_joint else 150000
                deduction_limit = max(0.0, apply_phaseout(total_income, max_deduction, phase_start))
                total_deduction = min(qoc_gross, deduction_limit)
                
                if base_salary_est <= 0:
                    error_msg = t["error_income_less_than_ot"]
                    st.session_state.calc_error = error_msg
                    st.error(error_msg)
                    
                else:
                    # Guardar resultados
                    st.session_state.results = {
                        "total_income": total_income,
                        "base_salary_est": base_salary_est,
                        "ot_total_paid": ot_total_paid,
                        "ot_1_5_total": ot_hours_1_5 * regular_rate * 1.5 if b_complete else ot_1_5_total,
                        "ot_2_0_total": dt_hours_2_0 * regular_rate * 2 if b_complete else ot_2_0_total,
                        "ot_1_5_premium": ot_1_5_premium,
                        "ot_2_0_premium": ot_2_0_premium,
                        "deduction_limit": deduction_limit,
                        "method_used": method_used,
                        "over_40": over_40,
                        "ot_1_5x": ot_1_5x,
                        "ss_check": ss_check,
                        "filing_status": filing_status,
                        "itin_check": itin_check,
                        "qoc_gross": qoc_gross,
                        "total_deduction": total_deduction,
                        "rate_1_5": rate_1_5,
                        "rate_2_0": rate_2_0
                    }
                    st.session_state.show_results = True
        
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
            st.success(t["total_deduction_no_limit"].format(format_number(total_deduction)))
        else:
            st.warning(t["total_deduction_with_limit"].format(format_number(total_deduction)))
            st.info(t["limit_info"].format(f'\\{format_number(qoc_gross)}', f'\\{format_number(deduction_limit)}'))

        st.markdown("---")

        col_left_res, col_right_res = st.columns([1, 2])

        with col_left_res:
            st.metric(
                label=t["total_deduction_label"],
                value=format_number(total_deduction),
                delta=t["total_deduction_delta"]
            )
            st.success(t["total_deduction_success"])

        with col_right_res:
            st.subheader(t["breakdown_subtitle"])
            st.metric(t["qoc_gross_label"], format_number(qoc_gross))
            st.metric(t["phaseout_limit_label"], format_number(deduction_limit))
            st.metric(t["final_after_limit_label"], format_number(total_deduction), delta_color="normal")
            
    # ────────────────────────────────────────────────
    # TABLA DE RESULTADOS
    # ────────────────────────────────────────────────
    with tab_data:
        st.subheader(t["data_subtitle"])
        data = st.session_state.results
        data_summary = {
            t["data_column_concept"]: t["data_concepts"],
            t["data_column_value"]: [
                format_number(data["total_income"]),
                format_number(data["base_salary_est"]),
                format_number(data["ot_1_5_total"]),
                "--" if not data["ot_2_0_total"] else format_number(data["ot_2_0_total"]),
                format_number(data["ot_total_paid"]),
                format_number(data["ot_1_5_premium"]),
                "--" if not data["ot_2_0_premium"] else format_number(data["ot_2_0_premium"]),
                "--" if not data["rate_1_5"] else format_number(data["rate_1_5"]),
                "--" if not data["rate_2_0"] else format_number(data["rate_2_0"]),
                format_number(data['deduction_limit']),
                data["method_used"],
                data["over_40"],
                data["ot_1_5x"],
                data["filing_status"],
                data["ss_check"],
                data["itin_check"],
            ]
        }
        st.dataframe(pd.DataFrame(data_summary), width='stretch')

# ────────────────────────────────────────────────
# DESCARGA DE REPORTE PDF – CORRECTED VERSION
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
    num_docs = len(uploaded_files) if uploaded_files is not None else 0

    if st.button(t["download_button"], type="primary", use_container_width=True):
        if not user_name.strip():
            st.error(t["download_error_name"])
        else:
            with st.spinner(t["spinner_generating_pdf"]):
                pdf = FPDF(format="A4")
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_margins(20, 20, 20)
                pdf.add_page()

                EPW = pdf.w - 2 * pdf.l_margin  # effective page width

                # ────────────────────────────────────────────────
                # Helper Functions
                # ────────────────────────────────────────────────

                def section_title(text):
                    pdf.ln(6)
                    pdf.set_font("Helvetica", "B", 13)
                    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
                    pdf.set_draw_color(200, 200, 200)
                    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                    pdf.ln(4)

                def body_text(text, size=11):
                    pdf.set_font("Helvetica", "", size)
                    pdf.multi_cell(0, 6, text)
                    pdf.ln(2)

                def key_value(label, value):
                    label_width = 70
                    line_height = 6

                    x_start = pdf.get_x()
                    y_start = pdf.get_y()

                    # Label
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.multi_cell(label_width, line_height, label, border=0)

                    # Save where label ended vertically
                    y_after_label = pdf.get_y()

                    # Move to the right of label (same starting Y)
                    pdf.set_xy(x_start + label_width, y_start)

                    # Value
                    pdf.set_font("Helvetica", "", 11)
                    pdf.multi_cell(0, line_height, value)

                    # Move cursor to max Y reached
                    y_after_value = pdf.get_y()
                    pdf.set_y(max(y_after_label, y_after_value))

                def money_line(label, value):
                    key_value(label, value)

                # ────────────────────────────────────────────────
                # DISCLAIMER PAGE
                # ────────────────────────────────────────────────

                pdf.set_font("Helvetica", "B", 15)
                pdf.cell(0, 10, t["disclaimer_label"], new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.ln(6)

                body_text(t["disclaimer_msg"], size=11)

                pdf.add_page()

                # ────────────────────────────────────────────────
                # HEADER
                # ────────────────────────────────────────────────

                pdf.set_font("Helvetica", "B", 16)
                pdf.cell(0, 10, t["pdf_title"], new_x="LMARGIN", new_y="NEXT", align="C")

                pdf.set_font("Helvetica", "", 11)
                pdf.cell(0, 6, t["pdf_generated_by"], new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.cell(
                    0,
                    6,
                    t["pdf_date"].format(datetime.now().strftime("%Y-%m-%d %H:%M")),
                    new_x="LMARGIN",
                    new_y="NEXT",
                    align="C"
                )

                pdf.ln(10)

                key_value(t["pdf_user_name"].replace("{}", ""), user_name)
                key_value(t["pdf_used_count"].replace("{}", ""), str(num_docs))

                # ────────────────────────────────────────────────
                # DATA SUMMARY
                # ────────────────────────────────────────────────

                data = st.session_state.results

                section_title(t["pdf_summary_title"])

                summary_items = [
                    (t["data_concepts"][0], format_number(data["total_income"])),
                    (t["data_concepts"][1], format_number(data["base_salary_est"])),
                    (t["data_concepts"][4], format_number(data["ot_total_paid"])),
                    (t["data_concepts"][5], format_number(data["ot_1_5_premium"])),
                    (t["data_concepts"][6], format_number(data["ot_2_0_premium"])),
                    (t["data_concepts"][9], format_number(data["deduction_limit"])),
                    (t["data_concepts"][10], data["method_used"]),
                ]

                for label, value in summary_items:
                    key_value(label + ":", value)

                # ────────────────────────────────────────────────
                # RESULTS SECTION
                # ────────────────────────────────────────────────

                section_title(t["pdf_results_title"])

                money_line(t["total_deduction_label"] + ":", format_number(data["total_deduction"]))
                money_line(t["qoc_gross_label"] + ":", format_number(data["qoc_gross"]))
                money_line(t["phaseout_limit_label"] + ":", format_number(data["deduction_limit"]))

                # Highlight final deduction
                pdf.ln(6)
                pdf.set_font("Helvetica", "B", 13)
                pdf.set_text_color(0, 102, 0)
                pdf.multi_cell(0, 8, t["pdf_final_deduction"].format_number(data["total_deduction"]))
                pdf.set_text_color(0, 0, 0)

                # ────────────────────────────────────────────────
                # EVIDENCE SECTION
                # ────────────────────────────────────────────────

                section_title(t["pdf_evidence_title"])

                if uploaded_files:
                    body_text(t["pdf_docs_attached"].format(len(uploaded_files)))
                else:
                    body_text(t["pdf_no_docs"])

                # ────────────────────────────────────────────────
                # GENERATE FINAL PDF
                # ────────────────────────────────────────────────

                pdf_bytes = pdf.output()

                merger = PdfMerger()
                merger.append(BytesIO(pdf_bytes))

                if uploaded_files:
                    for uploaded_file in uploaded_files:
                        merger.append(BytesIO(uploaded_file.read()))

                final_io = BytesIO()
                merger.write(final_io)
                merger.close()

                final_bytes = final_io.getvalue()

                st.download_button(
                    label=t["download_button_now"],
                    data=final_bytes,
                    file_name=f"Reporte_Deduccion_Horas_Extras_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                )

# Footer
st.markdown("---")
st.caption(t["footer"].format(date=datetime.now().strftime("%Y-%m-%d")))
