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
    page_title="Calculadora Deducción Horas Extras 2025",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ────────────────────────────────────────────────
# TEXTOS COMPLETOS – DICCIONARIO 100% COMPLETO Y ACTUALIZADO
# ────────────────────────────────────────────────
texts = {
    "es": {
        "title": "Calculadora de Deducción por Horas Extras (Ley OBBB 2025)",
        "desc": "Estima cuánto dinero extra de tus horas extras puedes quitar de tus impuestos federales en 2025 (hasta \\$12,500 o \\$25,000 según tu situación).",
        "flsa_title": "Paso 1: ¿Cumples con los requisitos básicos? (obligatorio)",
        "married_separated_label": "¿Eres casado presentando declaración por separado?",
        "over_40_label": "¿Te pagan horas extras por trabajar más de 40 horas a la semana?",
        "ot_1_5x_label": "¿La mayoría de tus horas extras se pagan a tiempo y medio (1.5x tu tarifa normal)?",
        "unlock_message": "Según tus respuestas, es posible que no califiques automáticamente. Consulta con un contador antes de usar esta calculadora. Si aun deseas proseguir, haz click abajo para confirmar que calificas de todos modos",
        "override_button": "Sí califico y quiero continuar de todos modos",
        "override_success": "¡Genial! Has confirmado manualmente que calificas.",
        "eligible_blocked_info": "**Las respuestas de elegibilidad están bloqueadas.** Si necesitas cambiarlas, usa el botón de abajo.",
        "eligible_auto_success": "¡Excelente! Cumples los requisitos automáticamente.",
        "reiniciar_button": "🔄 Reiniciar respuestas de elegibilidad",
        "income_title": "Paso 2: Ingresa tus datos de ingresos y horas extras",
        "magi_label": "Tu ingreso total aproximado del año (incluye horas extras, bonos, etc.) (\\$)",
        "filing_label": "Estado civil al presentar impuestos",
        "filing_options": ["Soltero o Cabeza de Familia", "Casado presentando declaración conjunta"],
        "calc_button": "Calcular mi deducción estimada",
        "results_title": "Tus resultados estimados",
        "footer": "Actualizado en {date} • Esta es solo una estimación – consulta siempre a un profesional de impuestos",
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
        "step3_info": "**Puedes usar una de estas dos formas** (o ambas si quieres comparar resultados):\n"
                      "- **Opción A – Más rápida** (por monto total recibido):\n"  
                      "  Úsala si solo tienes el importe total que te pagaron por horas extras (en tus recibos o W-2).\n"
                      "  Es más simple, pero menos precisa si hubo pagos a doble tiempo o tarifas diferentes.\n"
                      "\n"
                      "- **Opción B – Más precisa** (por horas trabajadas):\n"
                      "  Úsala si tienes registro de las horas extras trabajadas y tu tarifa horaria normal.\n"  
                      "  Es la forma más exacta, especialmente si tuviste horas a 1.5x y a 2.0x.",
                      
        # Opción A
        "option_a_title": "**Opción A** (por monto total pagado)",
        "ot_total_paid_label": "Monto TOTAL que te pagaron por horas extras este año (\\$)",
        "ot_total_paid_help": "Revisa tus recibos de pago o W-2. Suma **todo** lo recibido por horas extras.",
        "ot_multiplier_label": "La mayoría de tus horas extras se pagan a...",
        "ot_multiplier_options": ["1.5x (tiempo y medio)", "2.0x (doble tiempo)"],
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
        "ot_hours_1_5_label": "Horas totales en el año pagadas a tiempo y medio (1.5x) (numero de horas)",
        "ot_hours_1_5_help": "Suma de **todas** las horas extras que te pagaron a 1.5 veces durante el año.",
        "dt_hours_2_0_label": "Horas totales en el año pagadas a doble tiempo (2.0x) (numero de horas)",
        "dt_hours_2_0_help": "Horas pagadas al doble (ej: fines de semana o turnos especiales).",

        # Mensajes de ayuda FLSA
        "flsa_non_exempt_help": "La mayoría de los trabajos por hora son 'no exentos'. Si tu jefe te paga horas extras por ley, probablemente sí.",
        "flsa_over_40_help": "¿Te pagan más cuando superas las 40 horas por semana? Eso es la regla principal.",
        "flsa_ot_1_5x_help": "¿Casi todo tu pago extra es 1.5 veces tu tarifa normal? (ej: \\$30 en vez de \\$20). Si es doble en algunos días, igual puede contar.",

        # Errores y métodos
        "error_no_data": "⚠️ Completa al menos una de las opciones para calcular.",
        "method_hours": "Por horas trabajadas (Opción B)",
        "method_total_combined": "Por monto total (Opción A - todo junto)",
        "method_total_premium": "Por monto total (Opción A - solo dinero extra)",

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

        # Resultados
        "results_tab_title": "Resultados y deducción",
        "deduction_real_label": "Deducción real que puedes usar",
        "deduction_real_delta": "Este es el monto final a restar de tus impuestos",
        "deduction_real_success": "Esta es la cantidad que puedes usar para linea 14 del schedule 1a. 💰",
        "deduction_real_no_limit": "**Puedes deducir ${}** por el dinero adicional que ganaste en horas extras.",
        "deduction_real_with_limit": "**Puedes deducir ${}** por horas extras (limitado por tu ingreso total).",
        "limit_info": "Tu pago adicional por overtime fue de ${}, pero según tu ingreso total el máximo que puedes deducir es ${}. Por eso se reduce a esta cantidad.",
        "breakdown_subtitle": "Desglose detallado",
        "qoc_gross_label": "Dinero adicional ganado por horas extras (1.5x + 2.0x)",
        "phaseout_limit_label": "Límite máximo permitido por tu ingreso total",
        "reduction_label": "Reducción aplicada",
        "final_after_limit_label": "**Deducción final después de comparar ambos valores**",

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
        "pdf_generated_by": "Generado por Calculadora Deducción Horas Extras",
        "pdf_date": "Fecha de generación: {}",
        "pdf_user_name": "Nombre del contribuyente: {}",
        "pdf_used_count": "Número de documentos utilizados: {}",
        "pdf_summary_title": "Resumen de Datos Ingresados",
        "pdf_results_title": "Resultados y Deducción Estimada",
        "pdf_evidence_title": "Documentos Adjuntos como Evidencia",
        "pdf_no_docs": "No se subieron documentos de evidencia."
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
# ELEGIBILIDAD FLSA
# ────────────────────────────────────────────────
eligible = st.session_state.eligible_override

with st.expander(t["flsa_title"], expanded=not eligible):
    non_exempt = st.radio(
        t["married_separated_label"],
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
    st.subheader(t["income_title"])
    filing_status = st.selectbox(t["filing_label"], t["filing_options"])
    total_income = st.number_input(
        t["magi_label"],
        min_value=0.0,
        value=0.0,
        step=1000.0
    )

    # Ejemplo
    st.markdown(f"### {t['step3_title']}")
    st.info(t["step3_info"])
    with st.expander(t["example_title"], expanded=False):
        st.markdown(t["example_text"])
        
    # Expanders para cada opción
    with st.expander(t["option_a_title"], expanded=False):
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

    with st.expander(t["option_b_title"], expanded=False):
        regular_rate = st.number_input(
            t["regular_rate_label"],
            min_value=0.0,
            value=0.0,
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

            # col_left, col_right = st.columns(2)

            # with col_left:
            #     st.subheader(t["option_a_title"])
            #     ot_total_paid = st.number_input(
            #         t["ot_total_paid_label"],
            #         min_value=0.0,
            #         value=0.0,
            #         step=100.0,
            #         help=t["ot_total_paid_help"]
            #     )
            #     ot_multiplier_str = st.radio(
            #         t["ot_multiplier_label"],
            #         t["ot_multiplier_options"],
            #         horizontal=True,
            #         key="mult_total"
            #     )
            #     amount_included = st.radio(
            #         t["amount_included_label"],
            #         t["amount_included_options"],
            #         horizontal=True,
            #         key="type_total",
            #         help=t["amount_included_help"]
            #     )

            # with col_right:
            #     st.subheader(t["option_b_title"])
            #     regular_rate = st.number_input(
            #         t["regular_rate_label"],
            #         min_value=0.0,
            #         value=0.0,
            #         step=0.5,
            #         help=t["regular_rate_help"]
            #     )
            #     ot_hours_1_5 = st.number_input(
            #         t["ot_hours_1_5_label"],
            #         min_value=0.0,
            #         value=0.0,
            #         step=5.0,
            #         help=t["ot_hours_1_5_help"]
            #     )
            #     dt_hours_2_0 = st.number_input(
            #         t["dt_hours_2_0_label"],
            #         min_value=0.0,
            #         value=0.0,
            #         step=5.0,
            #         help=t["dt_hours_2_0_help"]
            #     )

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

        deduction_real = min(qoc_gross, final_deduction)

        # Guardar resultados
        st.session_state.results = {
            "filing_status": filing_status,
            "total_income": total_income,
            "base_salary_est": base_salary_est,
            "ot_total_shown": ot_total_shown,
            "payment_additional_1_5": payment_additional_1_5,
            "payment_additional_2_0": payment_additional_2_0,
            "method_used": method_used,
            "non_exempt": non_exempt,
            "over_40": over_40,
            "ot_1_5x": ot_1_5x,
            "qoc_gross": qoc_gross,
            "final_deduction": final_deduction,
            "reduction_amount": reduction_amount,
            "deduction_real": deduction_real
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
        final_deduction = data["final_deduction"]
        reduction_amount = data["reduction_amount"]
        deduction_real = data["deduction_real"]

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
    
    with tab_data:
        st.subheader(t["data_subtitle"])
        data = st.session_state.results
        data_summary = {
            "Concepto": t["data_concepts"],
            "Valor": [
                data["filing_status"],
                format_money(data["total_income"]),
                format_money(data["base_salary_est"]),
                format_money(data["ot_total_shown"]),
                format_money(data["payment_additional_1_5"]),
                format_money(data["payment_additional_2_0"]),
                data["method_used"],
                data["non_exempt"],
                data["over_40"],
                data["ot_1_5x"]
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
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, t["pdf_title"], ln=True, align="C")
                pdf.set_font("Arial", "", 12)
                pdf.cell(0, 10, t["pdf_generated_by"], ln=True, align="C")
                pdf.cell(0, 10, t["pdf_date"].format(datetime.now().strftime("%Y-%m-%d %H:%M")), ln=True, align="C")
                pdf.ln(10)

                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, t["pdf_user_name"].format(user_name), ln=True)
                pdf.cell(0, 10, t["pdf_used_count"].format(num_docs), ln=True)
                pdf.ln(10)

                # Resumen (igual que antes)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, t["pdf_summary_title"], ln=True)
                pdf.set_font("Arial", "", 10)

                data = st.session_state.results
                summary_lines = [
                    f"{t['data_concepts'][0]}: {data['filing_status']}",
                    f"{t['data_concepts'][1]}: {format_money(data['total_income'])}",
                    f"{t['data_concepts'][2]}: {format_money(data['base_salary_est'])}",
                    f"{t['data_concepts'][3]}: {format_money(data['ot_total_shown'])}",
                    f"{t['data_concepts'][4]}: {format_money(data['payment_additional_1_5'])}",
                    f"{t['data_concepts'][5]}: {format_money(data['payment_additional_2_0'])}",
                    f"{t['data_concepts'][6]}: {data['method_used']}",
                ]
                for line in summary_lines:
                    pdf.multi_cell(0, 8, line)

                pdf.ln(10)

                # Resultados
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, t["pdf_results_title"], ln=True)
                pdf.set_font("Arial", "", 10)
                pdf.multi_cell(0, 8, f"{t['deduction_real_label']}: {format_money(data['deduction_real'])}")
                pdf.multi_cell(0, 8, f"{t['qoc_gross_label']}: {format_money(data['qoc_gross'])}")
                pdf.multi_cell(0, 8, f"{t['phaseout_limit_label']}: {format_money(data['final_deduction'])}")
                if data['reduction_amount'] > 0:
                    pdf.multi_cell(0, 8, f"{t['reduction_label']}: -{format_money(data['reduction_amount'])}")

                pdf.ln(10)

                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, t["pdf_evidence_title"], ln=True)
                pdf.set_font("Arial", "", 10)
                if uploaded_files:
                    pdf.multi_cell(0, 8, f"Se adjuntan {len(uploaded_files)} documento(s) como evidencia.")
                else:
                    pdf.multi_cell(0, 8, t["pdf_no_docs"])

                # Guardar PDF principal
                main_pdf_path = tempfile.mktemp(suffix=".pdf")
                pdf.output(main_pdf_path)

                # Combinar
                merger = PdfMerger()
                merger.append(main_pdf_path)

                temp_upload_paths = []
                if uploaded_files:
                    for uploaded_file in uploaded_files:
                        tmp_path = tempfile.mktemp(suffix=".pdf")
                        with open(tmp_path, "wb") as tmp_upload:
                            tmp_upload.write(uploaded_file.read())
                        merger.append(tmp_path)
                        temp_upload_paths.append(tmp_path)

                final_pdf_path = tempfile.mktemp(suffix=".pdf")
                merger.write(final_pdf_path)
                merger.close()

                # Limpieza de archivos temporales
                os.unlink(main_pdf_path)
                for path in temp_upload_paths:
                    try:
                        os.unlink(path)
                    except PermissionError:
                        pass  # Windows puede tardar en liberar el handle

                # Descarga
                with open(final_pdf_path, "rb") as f:
                    st.download_button(
                        label="Descargar Reporte PDF Ahora",
                        data=f,
                        file_name=f"Reporte_Deduccion_Horas_Extras_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        key="download_pdf"
                    )

                # Limpieza final (puede fallar en Windows si el navegador lo tiene abierto)
                try:
                    os.unlink(final_pdf_path)
                except PermissionError:
                    pass

# Footer
st.markdown("---")
st.caption(t["footer"].format(date=datetime.now().strftime("%Y-%m-%d")))