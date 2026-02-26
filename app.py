import streamlit as st
import pandas as pd
from datetime import datetime
from logic import calculate_ot_premium, apply_phaseout
from fpdf import FPDF
from PyPDF2 import PdfMerger
from io import BytesIO


# ────────────────────────────────────────────────
# WEB TAB NAME AND LOGO
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="ZaiOT - Overtime Deduction Calculator",
    # page_icon="💼",   # You can also use a local image path
    layout="wide",
    initial_sidebar_state="collapsed"
    
)

# ────────────────────────────────────────────────
# BUTTONS COLOR
# ────────────────────────────────────────────────
st.markdown("""
<style>

/* ALL STREAMLIT BUTTONS → GREEN */
div[data-testid="stButton"] > button {
    background-color: #2ecc71 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.2s ease !important;
}

/* Hover */
div[data-testid="stButton"] > button:hover {
    background-color: #27ae60 !important;
    color: white !important;
    transform: translateY(-1px);
}

/* Active (click) */
div[data-testid="stButton"] > button:active {
    background-color: #219150 !important;
}

/* Remove gray disabled look */
div[data-testid="stButton"] > button:disabled {
    background-color: #2ecc71 !important;
    color: white !important;
    opacity: 0.6 !important;
}

</style>
""", unsafe_allow_html=True)

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
    
if "completed_step_2" not in st.session_state:
    st.session_state.completed_step_2 = False
    
if "completed_step_3" not in st.session_state:
    st.session_state.completed_step_3 = False

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
    
if "reset_eligibility" not in st.session_state:
    st.session_state.reset_eligibility = 0

# ────────────────────────────────────────────────
# TOP MAIN LOGO
# ────────────────────────────────────────────────
st.markdown(
    """
    <div style='text-align:center; margin-bottom:30px;'>
        <h1 style="
            font-size:52px;
            font-weight:800;
            letter-spacing:2px;
            background: linear-gradient(90deg, #1f6fd2, #7b61ff, #e53935);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom:5px;
        ">
            ZaiOT
        </h1>
        <p style="color:#666; font-size:15px;">
            OVERTIME DEDUCTION CALCULATOR
        </p>
    </div>
    """,
    unsafe_allow_html=True
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

def format_number(value: float, lang: str, currency="$", decimals=2) -> str:
    if value is None:
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
# TEXTOS EN DISPLAY
# ────────────────────────────────────────────────
texts = {
    "es": {
        "title": "Calculadora de Deducción por Horas Extras Calificadas (Ley OBBB 2025)",
        "desc": "Estimación de la deducción anual máxima aplicable a las horas extras calificadas (hasta $12,500 para declaración individual o $25,000 para declaración conjunta de casados).",
        "step1_title": "Paso 1: Verificación de requisitos básicos (obligatorio)",
        "step1_info": """
            Complete las preguntas de este paso para verificar si cumple con los requisitos básicos de elegibilidad.
            El sistema evaluará automáticamente las respuestas. Si no califica de forma automática,
            podrá confirmar manualmente su elegibilidad para continuar.
        """,
        "over_40_label": "¿Se compensan las horas trabajadas por encima de 40 semanales con pago de horas extras?",
        "ss_check_label": "¿El contribuyente posee un Número de Seguro Social (SSN) válido para trabajar?",
        "itin_check_label": "¿El contribuyente posee un Número de Identificación Tributaria Individual (ITIN)?",
        "ot_1_5x_label": "¿La mayoría de las horas extras se remuneran con una tarifa de tiempo y medio (1.5x la tarifa regular)?",
        "unlock_message": "De acuerdo con las respuestas proporcionadas, es posible que no se cumplan los requisitos para aplicar la deducción. Se recomienda consultar con un contador profesional antes de continuar. Si el usuario está seguro de cumplir con los criterios, puede proceder haciendo clic en el botón a continuación para confirmar y continuar manualmente.",
        "override_button": "Confirmo que cumplo los requisitos y deseo continuar",
        "override_success": "Se ha confirmado manualmente el cumplimiento de los requisitos.",
        "eligible_blocked_info": "**Las respuestas de elegibilidad se encuentran bloqueadas.** Para modificarlas, utilice el botón inferior.",
        "eligible_auto_success": "Se verificó que se cumplen los requisitos básicos de forma automática.",
        "reiniciar_button": "🔄 Reiniciar respuestas de elegibilidad",
        "step2_title": "Paso 2: Ingreso de datos de ingresos y horas extras",
        "step2_info": """
            Ingrese su ingreso total aproximado del año (incluyendo todos los conceptos gravables).
            Este dato es esencial para calcular la deducción máxima permitida según su nivel de ingresos.
        """,
        "magi_label": "Ingreso total aproximado del año (incluye salario base, horas extras, bonos, etc) ($)",
        "filing_status_label": "Estado civil para efectos de la declaración de impuestos",
        "filing_status_options": [
            "Soltero(a)",
            "Cabeza de familia",
            "Casado(a) presentando declaración conjunta",
            "Casado(a) presentando declaración por separado"
        ],
        "calculate_button": "Calcular deducción estimada",
        "results_title": "Resultados estimados",
        "footer": "Información actualizada al {date} \n Esta herramienta ofrece únicamente una estimación. Consulte siempre con un profesional de impuestos.",
        "answer_options": ["Sí", "No", "No estoy seguro(a)"],

        # Ejemplo y pasos
        "example_text": """
            Ejemplo ilustrativo:
            - Tarifa regular: \\$25 por hora
            - 10 horas extras remuneradas a tiempo y medio (1.5x)

            Cálculo:
            - Pago total recibido por esas horas: \\$375 (\\$25 × 1.5 × 10)
            - De ese monto:
              • \\$250 corresponden al salario base (\\$25 × 10)
              • \\$125 corresponden al pago adicional por horas extras (monto deducible)

            Opciones de ingreso:
            - Opción A (más rápida): registrar \\$375 como monto total pagado por horas extras.
            - Opción B (más precisa): indicar tarifa regular \\$25 + 10 horas a 1.5x.
        """,
        "step2_completed_msg": "✅ Paso 2 completado. Puede continuar con el Paso 3.",
        "step3_title": "Paso 3: Selección del método para ingresar datos de horas extras",
        "step3_info": """
            **Seleccione el método más conveniente y complete los campos correspondientes:**

            - **Opción A** — Ingreso por monto total recibido  
              Recomendada cuando se dispone únicamente del importe total pagado por horas extras (visible en recibos de pago o formulario W-2). Método rápido y suficiente en la mayoría de los casos.

            - **Opción B** — Ingreso por horas trabajadas y tarifa regular  
              Recomendada cuando se cuenta con el detalle exacto de horas laboradas y la tarifa horaria normal. Proporciona mayor precisión, especialmente cuando existen horas remuneradas a doble tarifa.

            **Nota:** Es necesario completar solamente uno de los dos métodos.
        """,
        "choose_method_label": "Seleccione el método para reportar las horas extras",
        "choose_method_options": [
            "Dispongo del monto total pagado por horas extras (Opción A)",
            "Dispongo del detalle de horas trabajadas y tarifa regular (Opción B)"
        ],

        # Opción A
        "option_a_title": "**Opción A** — Ingreso por monto total pagado",
        "ot_total_1_5_paid_label": "Monto total recibido por horas extras a tiempo y medio durante el año ($)",
        "ot_total_1_5_paid_help": "Sume todos los importes recibidos por concepto de horas extras remuneradas a tarifa de tiempo y medio, según recibos de pago o formulario W-2.",
        "ot_total_2_0_paid_label": "Monto total recibido por horas extras a doble tarifa durante el año ($)",
        "ot_total_2_0_paid_help": "Sume todos los importes recibidos por concepto de horas extras remuneradas al doble de la tarifa regular, según recibos de pago o formulario W-2.",

        # Opción B
        "option_b_title": "**Opción B** — Ingreso por horas trabajadas y tarifa regular",
        "regular_rate_label": "Tarifa horaria regular ($ por hora)",
        "regular_rate_help": "Indique el monto que se paga por hora de trabajo regular, sin incluir pagos adicionales por horas extras.",
        "ot_hours_1_5_label": "Horas totales remuneradas a tiempo y medio durante el año (número de horas)",
        "ot_hours_1_5_help": "Registre la suma total de horas extras remuneradas a tarifa de tiempo y medio (1.5x) durante el año.",
        "dt_hours_2_0_label": "Horas totales remuneradas a doble tarifa durante el año (número de horas)",
        "dt_hours_2_0_help": "Registre las horas remuneradas al doble de la tarifa regular (por ejemplo, fines de semana o turnos especiales).",

        # Mensajes de ayuda FLSA
        "over_40_help": "Indique si las horas trabajadas por encima de 40 semanales generan un pago adicional por concepto de horas extras, conforme a la normativa laboral aplicable.",
        "ot_1_5x_help": "Confirme si la mayor parte del pago adicional por horas extras corresponde a una tarifa de tiempo y medio (1.5x la tarifa regular).",
        "ss_check_help": "La deducción requiere que el contribuyente posea un Número de Seguro Social válido para empleo.",
        "itin_check_help": "La presencia de un ITIN en lugar de un SSN válido impide aplicar esta deducción.",

        # Errores y mensajes
        "error_no_data": "⚠️ Debe completar al menos uno de los métodos del Paso 3 para realizar el cálculo.",
        "error_empty_option_a": "⚠️ La Opción A está incompleta. Complete al menos uno de los montos para continuar.",
        "error_empty_option_b": "⚠️ La Opción B está incompleta. Ingrese la tarifa regular y al menos una cantidad de horas.",
        "error_missing_total_income": "⚠️ Debe ingresar el ingreso total aproximado del año para continuar.",
        "error_partial_option_b_conflict": "Se detectó información parcial en la Opción B. Complete todos los campos o elimine los datos ingresados para continuar.",
        "error_income_less_than_ot": "El ingreso total reportado parece ser inferior al monto total pagado por horas extras. Porfavor revise sus respuestas e intente denuevo",
        "error_option_a_b": "Se ingresaron datos en ambas opciones, pero los resultados no coinciden.\n\n"
                            "Opción A → Pago adicional estimado: {}\n"
                            "Opción B → Pago adicional estimado: {}",
        "warning_option_a_b": "Revise y corrija los valores ingresados para continuar.",
        "warning_no_method_chosen": "Debe seleccionar un método de ingreso de horas extras para continuar.",
        "method_hours": "Por horas trabajadas (Opción B)",
        "method_total": "Por monto total pagado (Opción A)",
        "method_a_and_b": "Ambas opciones (Opción A y B)",
        "error_pdf_generation": "❌ Error generating PDF: {}",

        # Resumen de datos
        "data_tab_title": "Resumen de información ingresada",
        "data_subtitle": "Información proporcionada por el usuario",
        "data_concepts": [
            "Ingreso total aproximado del año (base + extras)",
            "Salario base estimado (ingreso total sin pago adicional por extras)",
            "Total pagado por horas extras a tiempo y medio (base + extra)",
            "Total pagado por horas extras a doble tarifa (base + extra)",
            "Total pagado por concepto de horas extras",
            "Pago adicional por horas extras a 1.5x (deducible)",
            "Pago adicional por horas extras a 2.0x (deducible)",
            "Tarifa horaria por horas extras a 1.5x",
            "Tarifa horaria por horas extras a 2.0x",
            "Límite máximo deducible según ingresos",
            "Método de cálculo utilizado",
            "¿Se compensan las horas por encima de 40 semanales con pago de horas extras?",
            "¿La mayoría de las horas extras se pagan a tiempo y medio?",
            "Estado civil para la declaración de impuestos",
            "¿Posee un Número de Seguro Social válido para trabajar?",
            "¿Posee un Número de Identificación Tributaria Individual (ITIN)?"
        ],

        # Resultados
        "data_column_concept": "Concepto",
        "data_column_value": "Valor",
        "results_tab_title": "Resultados y deducción estimada",
        "total_deduction_label": "Deducción aplicable en la línea 14 del Schedule 1 (Formulario 1040)",
        "total_deduction_delta": "Monto final a deducir de la base imponible",
        "total_deduction_success": "Esta es la cantidad que puede utilizar en la línea 14 del Schedule 1. 💰",
        "total_deduction_no_limit": "**Puede deducir {}** correspondiente al pago adicional por horas extras calificadas.",
        "total_deduction_with_limit": "**Puede deducir {}** por concepto de horas extras (limitado por el nivel de ingresos).",
        "limit_info": "El pago adicional por horas extras ascendió a {}, pero de acuerdo con el ingreso total, el monto máximo deducible es {}. Por ello se ajusta a esta cantidad.",
        "breakdown_subtitle": "Desglose detallado",
        "qoc_gross_label": "Monto total correspondiente al pago adicional por horas extras",
        "phaseout_limit_label": "Límite máximo deducible según nivel de ingresos",
        "reduction_label": "Reducción aplicada por phase-out",
        "final_after_limit_label": "**Deducción final tras aplicar límite máximo permitido**",

        # Descarga PDF
        "spinner_generating_pdf": "Generando reporte PDF...",
        "generate_pdf": "Generar reporte PDF",
        "generated_pdf_success": "Reporte generado exitosamente",
        "generated_pdf_success_info": "El documento ya está listo. Puede descargarlo utilizando el botón inferior.",
        "download_button_now": "Descargar Reporte PDF",
        "download_section_title": "Generación y descarga del reporte",
        "download_name_label": "Nombre completo del contribuyente (aparecerá en el reporte)",
        "download_name_placeholder": "Ejemplo: Juan Pérez",
        "download_w2_options": ["1", "2", "3 o más"],
        "download_docs_label": "Adjuntar documentos de respaldo (W-2, recibos de pago, etc.) – opcional pero recomendado",
        "download_docs_help": "Puede cargar uno o varios archivos PDF. Estos se incorporarán al final del reporte generado.",
        "download_button": "Generar y Descargar Reporte PDF",
        "download_error_name": "Debe ingresar el nombre completo para generar el reporte.",
        "pdf_title": "Reporte de Deducción por Horas Extras Calificadas – Ley OBBB 2025",
        "pdf_generated_by": "Hecho por ZaiOT",
        "pdf_date": "Fecha: {}",
        "pdf_user_name": "Nombre del contribuyente: {}",
        "pdf_used_count": "Cantidad de documentos adjuntos: {}",
        "pdf_summary_title": "Resumen de información ingresada",
        "pdf_results_title": "Resultados y deducción estimada",
        "pdf_evidence_title": "Documentos adjuntos como evidencia",
        "pdf_no_docs": "No se adjuntaron documentos de respaldo.",
        "pdf_docs_attached": "Se adjuntan {} documento(s) como evidencia.",
        "pdf_final_deduction": "DEDUCCIÓN FINAL ESTIMADA: {}",

        # Disclaimer
        "disclaimer_label": "AVISO LEGAL Y DESCARGO DE RESPONSABILIDAD",
        "disclaimer": "**Descargo de responsabilidad:** Esta herramienta tiene únicamente fines informativos y de estimación. No constituye ni sustituye asesoría profesional en materia tributaria.",
        "disclaimer_msg": "IMPORTANTE: Esta calculadora genera estimaciones aproximadas de la deducción por horas extras calificadas conforme a la Ley OBBB 2025. "
                          "No representa asesoría fiscal, legal ni contable. Los resultados son orientativos y no garantizan su aceptación por parte del IRS. "
                          "Se recomienda consultar con un contador público autorizado o profesional tributario certificado antes de incluir cualquier deducción en una declaración de impuestos. "
                          "El uso de esta herramienta es bajo exclusiva responsabilidad del usuario.",

        # Language
        "language_label": "🌐 Idioma",
        "language_options": ["Español", "English"],

        # Button Labels
        "button_continue": "Continuar"
    },
    
    "en": {  # Versión en inglés
        "title": "Qualified Overtime Deduction Calculator (OBBB Act 2025)",
        "desc": "Estimate of the maximum annual deduction applicable to qualified overtime pay (up to $12,500 for single filers or $25,000 for married filing jointly).",
        "step1_title": "Step 1: Basic Eligibility Check (required)",
        "step1_info": """
            Please answer the questions below to verify if you meet the basic eligibility requirements.
            The system will automatically evaluate your responses. If you do not qualify automatically,
            you will have the option to manually confirm your eligibility and continue.
        """,
        "over_40_label": "Are hours worked over 40 per week compensated with overtime pay?",
        "ss_check_label": "Does the taxpayer have a valid Social Security Number (SSN) for employment?",
        "itin_check_label": "Does the taxpayer have an Individual Taxpayer Identification Number (ITIN)?",
        "ot_1_5x_label": "Are most overtime hours paid at time-and-a-half rate (1.5x the regular rate)?",
        "unlock_message": "Based on the responses provided, it appears the requirements for this deduction may not be met. It is recommended to consult a tax professional before proceeding. If you are certain you meet the criteria, please click the button below to manually confirm and continue.",
        "override_button": "I confirm I meet the requirements and wish to continue",
        "override_success": "Manual confirmation of eligibility has been recorded.",
        "eligible_blocked_info": "**Eligibility responses are currently locked.** To modify them, use the button below.",
        "eligible_auto_success": "Basic eligibility requirements have been automatically verified.",
        "reiniciar_button": "🔄 Reset eligibility responses",
        "step2_title": "Step 2: Enter Income and Overtime Data",
        "step2_info": """
            Please enter your approximate total income for the year (including base salary, overtime, bonuses, and all other taxable income).
            This information is essential to determine the maximum allowable deduction based on your income level.
        """,
        "magi_label": "Approximate total annual income (includes base salary, overtime, bonuses, etc.) ($)",
        "filing_status_label": "Filing status for tax purposes",
        "filing_status_options": [
            "Single",
            "Head of Household",
            "Married Filing Jointly",
            "Married Filing Separately"
        ],
        "calculate_button": "Calculate Estimated Deduction",
        "results_title": "Estimated Results",
        "footer": "Information updated as of {date} \n This tool provides an estimate only. Always consult a tax professional.",
        "answer_options": ["Yes", "No", "Not sure"],

        # Example and instructions
        "example_text": """
            Illustrative example:
            - Regular rate: $25 per hour
            - 10 overtime hours paid at time-and-a-half (1.5x)

            Calculation:
            - Total pay received for those hours: $375 ($25 × 1.5 × 10)
            - Of that amount:
              • $250 corresponds to base pay ($25 × 10)
              • $125 corresponds to the overtime premium (deductible portion)

            Input options:
            - Option A (faster): enter $375 as total overtime pay received.
            - Option B (more precise): enter regular rate $25 + 10 hours at 1.5x.
        """,
        "step2_completed_msg": "✅ Step 2 completed. You may proceed to Step 3.",
        "step3_title": "Step 3: Select Method to Enter Overtime Data",
        "step3_info": """
            **Choose the most convenient method and complete the corresponding fields:**

            - **Option A** — Enter total amount received  
              Recommended when you only have the total overtime pay amount (shown on pay stubs or W-2). Quick and sufficient in most cases.

            - **Option B** — Enter hours worked and regular rate  
              Recommended when you have the exact breakdown of hours and regular hourly rate. Provides greater accuracy, especially if double-time hours were paid.

            **Note:** You only need to complete one of the two methods.
        """,
        "choose_method_label": "Select the method for reporting overtime",
        "choose_method_options": [
            "I have the total amount paid for overtime (Option A)",
            "I have the breakdown of hours worked and regular rate (Option B)"
        ],

        # Option A
        "option_a_title": "**Option A** — Total amount paid",
        "ot_total_1_5_paid_label": "Total amount received for time-and-a-half overtime during the year ($)",
        "ot_total_1_5_paid_help": "Sum all amounts received for overtime paid at time-and-a-half rate, according to pay stubs or Form W-2.",
        "ot_total_2_0_paid_label": "Total amount received for double-time overtime during the year ($)",
        "ot_total_2_0_paid_help": "Sum all amounts received for overtime paid at double the regular rate, according to pay stubs or Form W-2.",

        # Option B
        "option_b_title": "**Option B** — Hours worked and regular rate",
        "regular_rate_label": "Regular hourly rate ($ per hour)",
        "regular_rate_help": "Enter the amount paid per hour for regular work, excluding any overtime premiums.",
        "ot_hours_1_5_label": "Total hours paid at time-and-a-half during the year (number of hours)",
        "ot_hours_1_5_help": "Enter the total number of overtime hours paid at 1.5x the regular rate during the year.",
        "dt_hours_2_0_label": "Total hours paid at double time during the year (number of hours)",
        "dt_hours_2_0_help": "Enter hours paid at double the regular rate (e.g., weekends or special shifts).",

        # FLSA help messages
        "over_40_help": "Indicate whether hours worked over 40 per week are compensated with overtime pay under applicable labor regulations.",
        "ot_1_5x_help": "Confirm whether most overtime premium pay is at the time-and-a-half rate (1.5x regular rate).",
        "ss_check_help": "This deduction requires the taxpayer to have a valid Social Security Number for employment.",
        "itin_check_help": "Having an ITIN instead of a valid SSN prevents eligibility for this deduction.",

        # Errors and messages
        "error_no_data": "⚠️ You must complete at least one method in Step 3 to perform the calculation.",
        "error_empty_option_a": "⚠️ Option A is incomplete. Please enter at least one amount to continue.",
        "error_empty_option_b": "⚠️ Option B is incomplete. Please enter the regular rate and at least one hour amount.",
        "error_missing_total_income": "⚠️ You must enter the approximate total annual income to continue.",
        "error_partial_option_b_conflict": "Partial information detected in Option B. Please complete all fields or clear the data to continue.",
        "error_income_less_than_ot": "The reported total income seems to be less than the total overtime pay amount. Please check your anwsers and try again.",
        "error_option_a_b": "Data was entered in both options, but the results do not match.\n\n"
                            "Option A → Estimated premium pay: {}\n"
                            "Option B → Estimated premium pay: {}",
        "warning_option_a_b": "Please review and correct the entered values to continue.",
        "warning_no_method_chosen": "You must select a method for entering overtime data to continue.",
        "method_hours": "By hours worked (Option B)",
        "method_total": "By total amount paid (Option A)",
        "method_a_and_b": "Both options (A and B)",
        "error_pdf_generation": "❌ Error al general el PDF: {}",

        # Data summary
        "data_tab_title": "Summary of Entered Information",
        "data_subtitle": "Information provided by the user",
        "data_concepts": [
            "Approximate total annual income (base + overtime)",
            "Estimated base salary (total income excluding overtime premium)",
            "Total paid for time-and-a-half overtime (base + premium)",
            "Total paid for double-time overtime (base + premium)",
            "Total paid for overtime",
            "Overtime premium at 1.5x (deductible)",
            "Overtime premium at 2.0x (deductible)",
            "Hourly rate for 1.5x overtime",
            "Hourly rate for 2.0x overtime",
            "Maximum deductible limit based on income",
            "Calculation method used",
            "Are hours over 40 per week compensated with overtime pay?",
            "Are most overtime hours paid at time-and-a-half?",
            "Filing status for tax return",
            "Has a valid Social Security Number for employment?",
            "Has an Individual Taxpayer Identification Number (ITIN)?"
        ],

        # Results
        "data_column_concept": "Concept",
        "data_column_value": "Value",
        "results_tab_title": "Results and Estimated Deduction",
        "total_deduction_label": "Deduction applicable on line 14 of Schedule 1 (Form 1040)",
        "total_deduction_delta": "Final amount to be deducted from taxable income",
        "total_deduction_success": "This is the amount you can use on line 14 of Schedule 1. 💰",
        "total_deduction_no_limit": "**You may deduct {}** corresponding to qualified overtime premium pay.",
        "total_deduction_with_limit": "**You may deduct {}** for overtime (limited by income level).",
        "limit_info": "The overtime premium amounted to {}, but based on total income, the maximum allowable deduction is {}. The amount has been adjusted accordingly.",
        "breakdown_subtitle": "Detailed Breakdown",
        "qoc_gross_label": "Total qualified overtime premium amount",
        "phaseout_limit_label": "Maximum deductible limit based on income level",
        "reduction_label": "Reduction due to phase-out",
        "final_after_limit_label": "**Final deduction after applying maximum limit**",

        # PDF Download
        "spinner_generating_pdf": "Generating PDF report...",
        "generate_pdf": "Generate PDF Report",
        "generated_pdf_success": "Report generated successfully",
        "generated_pdf_success_info": "The document is ready. You may now download the report below.",
        "download_button_now": "Download PDF Report",
        "download_section_title": "Report Generation and Download",
        "download_name_label": "Taxpayer's full name (will appear on the report)",
        "download_name_placeholder": "Example: John Pérez",
        "download_w2_options": ["1", "2", "3 or more"],
        "download_docs_label": "Attach supporting documents (W-2, pay stubs, etc.) – optional but recommended",
        "download_docs_help": "You may upload one or more PDF files. They will be appended to the end of the generated report.",
        "download_button": "Generate and Download PDF Report",
        "download_error_name": "Please enter your full name to generate the report.",
        "pdf_title": "Qualified Overtime Deduction Report – OBBB Act 2025",
        "pdf_generated_by": "Made by ZaiOT",
        "pdf_date": "Date: {}",
        "pdf_user_name": "Taxpayer name: {}",
        "pdf_used_count": "Number of attached documents: {}",
        "pdf_summary_title": "Summary of Entered Information",
        "pdf_results_title": "Results and Estimated Deduction",
        "pdf_evidence_title": "Supporting Documents Attached",
        "pdf_no_docs": "No supporting documents were attached.",
        "pdf_docs_attached": "{} document(s) attached as evidence.",
        "pdf_final_deduction": "FINAL ESTIMATED DEDUCTION: {}",

        # Disclaimer
        "disclaimer_label": "LEGAL NOTICE AND DISCLAIMER",
        "disclaimer": "**Disclaimer:** This tool is provided for informational and estimation purposes only. It does not constitute or replace professional tax advice.",
        "disclaimer_msg": "IMPORTANT: This calculator generates approximate estimates of the qualified overtime deduction under the OBBB Act 2025. "
                          "It is not tax, legal, or accounting advice. Results are for guidance only and do not guarantee acceptance by the IRS. "
                          "It is strongly recommended to consult a certified public accountant or qualified tax professional before claiming any deduction on a tax return. "
                          "Use of this tool is at the user's sole responsibility.",

        # Language
        "language_label": "🌐 Language",
        "language_options": ["Spanish", "English"],

        # Button Labels
        "button_continue": "Continue"
    }
}
# Idioma

# Inicializamos idioma por defecto si no existe
if "language" not in st.session_state:
    st.session_state.language = "es"
    
# Mostramos el selector (usamos el valor actual de session_state)
current_index = 0 if st.session_state.language == "es" else 1

# Load dict to display correct words on language selection
t = texts[st.session_state.language]

# Mostramos el selector
lang_selected = st.selectbox(
    t["language_label"],
    t["language_options"],
    index=current_index,
    label_visibility="visible",
    key="global_language_selector",
)

# Map selected option → language code using BOTH languages' option texts
new_language = "es" if lang_selected in ("Español", "Spanish") else "en"

if new_language != st.session_state.language:
    st.session_state.language = new_language
    st.rerun()
    
# Cargamos los textos con el idioma actual
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
    
    st.info(t["step1_info"])
    
    filing_status = st.radio(
        t["filing_status_label"],
        t["filing_status_options"],
        index=None,
        horizontal=True,
        disabled=eligible,
        key=f"filing_status_radio_{st.session_state.reset_eligibility}"
    )
    
    over_40 = st.radio(
        t["over_40_label"],
        t["answer_options"],
        index=None,
        horizontal=True,
        disabled=eligible,
        help=t["over_40_help"],
        key=f"over_40_radio_{st.session_state.reset_eligibility}"
    )
    ot_1_5x = st.radio(
        t["ot_1_5x_label"],
        t["answer_options"],
        index=None,
        horizontal=True,
        disabled=eligible,
        help=t["ot_1_5x_help"],
        key=f"ot_1_5x_radio_{st.session_state.reset_eligibility}"
    )
    ss_check = st.radio(
        t["ss_check_label"],
        t["answer_options"],
        index=None,
        horizontal=True,
        disabled=eligible,
        help=t["ss_check_help"],
        key=f"ss_check_radio_{st.session_state.reset_eligibility}"
    )
    itin_check = st.radio(
        t["itin_check_label"],
        t["answer_options"],
        index=None,
        horizontal=True,
        disabled=eligible,
        help=t["itin_check_help"],
        key=f"itin_check_radio_{st.session_state.reset_eligibility}"
    )
    
    partial_responses = (
        filing_status == None or 
        over_40 == None or 
        ot_1_5x == None or
        ss_check == None or
        itin_check == None
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
            st.session_state.reset_eligibility += 1
            st.rerun()
            
    elif not partial_responses:
        st.warning(t["unlock_message"])
        if st.button(t["override_button"], width='stretch', type="secondary"):
            st.session_state.eligible_override = True
            st.rerun()

# ────────────────────────────────────────────────
# SECCIÓN DE INGRESOS Y CÁLCULO
# ────────────────────────────────────────────────
if eligible:
    with st.expander(f"### {t['step2_title']}", expanded=True):
        st.info(t["step2_info"])
        
        total_income = pretty_money_input(
            t["magi_label"],
            value=0.0,
            step=1000.0,
            decimals=2,          
            help=None,
            lang=st.session_state.language
        )
        # ── Solo mostramos el botón si el paso NO está completado ──
        if not st.session_state.completed_step_2:
            if st.button(t["button_continue"], type="secondary", width="stretch"):
                if total_income <= 0:
                    st.error(t["error_missing_total_income"])
                else:
                    st.session_state.completed_step_2 = True
                    st.rerun()  # ← Fuerza la recarga para que el botón desaparezca inmediatamente

        # Si ya se completó, mostramos un mensaje de confirmación (opcional pero mejora UX)
        if st.session_state.completed_step_2:
            st.success(t["step2_completed_msg"])

        # Bloquea el avance si no se completó (ya lo tienes)
        if not st.session_state.completed_step_2:
            st.stop()

    with st.expander(f"### {t['step3_title']}", expanded=True):
        # Default safe values
        ot_1_5_total = 0.0
        ot_2_0_total = 0.0
        regular_rate = 0.0
        ot_hours_1_5 = 0.0
        dt_hours_2_0 = 0.0
        rate_1_5 = 0.0
        rate_2_0 = 0.0
        
        st.info(t["step3_info"])
        
        method_choice = st.radio(
            t["choose_method_label"],
            t["choose_method_options"],
            index=None,
            horizontal=True
        )
        
        # st.caption(t["example_text"])
        
        if not method_choice:
            st.warning(t["warning_no_method_chosen"])
            st.stop()
          
        elif method_choice == t["choose_method_options"][0]:
            # show Option A only
            with st.expander(t["option_a_title"], expanded=True):
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
        else:
            # show Option B only
            with st.expander(t["option_b_title"], expanded=True):
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
    if st.button(t["calculate_button"], type="secondary", width="stretch"):
        # -----------------------------------
        # STEP 1 — Validate Income and Selected Method
        # -----------------------------------
        if total_income <= 0:
            st.error(t["error_missing_total_income"])
            st.stop()
            
        if method_choice == t["choose_method_options"][0]:
            # OPTION A → User entered total overtime amounts
            a_complete = (ot_1_5_total > 0) or (ot_2_0_total > 0)
            if not a_complete:
                st.error(t["error_empty_option_a"])
                st.stop()
            method_used = t["method_total"]
            # Set overtime rates
            rate_1_5 = 0.0
            rate_2_0 = 0.0

        else:
            # OPTION B → User entered rate + hours
            b_complete = (regular_rate > 0) and ((ot_hours_1_5 + dt_hours_2_0) > 0)
            if not b_complete:
                st.error(t["error_empty_option_b"])
                st.stop()
            method_used = t["method_hours"]
            # Get overtime rates
            rate_1_5 = regular_rate * 1.5
            rate_2_0 = regular_rate * 2.0
            # Convert hours → total paid overtime amounts
            ot_1_5_total = ot_hours_1_5 * rate_1_5
            ot_2_0_total = dt_hours_2_0 * rate_2_0
            
        # -----------------------------------
        # STEP 2 — Calculate Premium Portion
        # -----------------------------------
        ot_total_paid = ot_1_5_total + ot_2_0_total
        ot_1_5_premium = calculate_ot_premium(
            ot_1_5_total,
            1.5,
            "total"
        )
        ot_2_0_premium = calculate_ot_premium(
            ot_2_0_total,
            2.0,
            "total"
        )
        qoc_gross = ot_1_5_premium + ot_2_0_premium

        # -----------------------------------
        # STEP 3 — Deduction Limit
        # -----------------------------------
        # Definir según filing status (usa los valores de OBBB 2025/2026)
        if filing_status == t["filing_status_options"][2]:  # "Casado presentando declaración conjunta"
            max_ded = 25000
            phase_start = 300000
            phase_range = 250000   # 550k - 300k
        else:
            # Soltero, Cabeza de Familia, Separado (nota: Separado suele no calificar, pero ya lo bloqueaste en elegibilidad)
            max_ded = 12500
            phase_start = 150000
            phase_range = 125000   # 275k - 150k
        
        deduction_limit = apply_phaseout(
            magi=total_income,
            max_value=max_ded,
            phase_start=phase_start,
            phase_range=phase_range
        )
        total_deduction = min(qoc_gross, deduction_limit)
        
        # -----------------------------------
        # STEP 4 — Base salary
        # -----------------------------------
        base_salary = total_income - ot_total_paid
        if base_salary < 0:
            st.error(t["error_income_less_than_ot"])
            st.stop()
        
        # -----------------------------------
        # Guardar resultados
        # -----------------------------------
        st.session_state.results = {
            "total_income": total_income,
            "base_salary": base_salary,
            "ot_total_paid": ot_total_paid,
            "ot_1_5_total": ot_1_5_total,
            "ot_2_0_total": ot_2_0_total,
            "ot_1_5_premium": ot_1_5_premium,
            "ot_2_0_premium": ot_2_0_premium,
            "rate_1_5": rate_1_5,
            "rate_2_0": rate_2_0,
            "method_used": method_used,
            "over_40": "--" if not over_40 else over_40,
            "ot_1_5x": "--" if not ot_1_5x else ot_1_5x,
            "ss_check": "--" if not ss_check else ss_check,
            "filing_status": "--" if not filing_status else filing_status,
            "itin_check": "--" if not itin_check else itin_check,
            "qoc_gross": qoc_gross,
            "deduction_limit": deduction_limit,
            "total_deduction": total_deduction
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
            st.success(t["total_deduction_no_limit"].format(format_number(total_deduction, st.session_state.language)))
        else:
            st.warning(t["total_deduction_with_limit"].format(format_number(total_deduction, st.session_state.language)))
            st.info(t["limit_info"].format(f"\\{format_number(qoc_gross, st.session_state.language)}", f"\\{format_number(deduction_limit, st.session_state.language)}"))

        st.markdown("---")

        col_left_res, col_right_res = st.columns([1, 2])

        with col_left_res:
            st.metric(
                label=t["total_deduction_label"],
                value=format_number(total_deduction, st.session_state.language),
                delta=t["total_deduction_delta"]
            )
            st.success(t["total_deduction_success"])

        with col_right_res:
            st.subheader(t["breakdown_subtitle"])
            st.metric(t["qoc_gross_label"], format_number(qoc_gross, st.session_state.language))
            st.metric(t["phaseout_limit_label"], format_number(deduction_limit, st.session_state.language))
            st.metric(t["final_after_limit_label"], format_number(total_deduction, st.session_state.language), delta_color="normal")
            
    # ────────────────────────────────────────────────
    # TABLA DE RESULTADOS
    # ────────────────────────────────────────────────
    with tab_data:
        st.subheader(t["data_subtitle"])
        data = st.session_state.results
        data_summary = {
            t["data_column_concept"]: t["data_concepts"],
            t["data_column_value"]: [
                format_number(data["total_income"], st.session_state.language),
                format_number(data["base_salary"], st.session_state.language),
                format_number(data["ot_1_5_total"], st.session_state.language),
                "--" if not data["ot_2_0_total"] else format_number(data["ot_2_0_total"], st.session_state.language),
                format_number(data["ot_total_paid"], st.session_state.language),
                format_number(data["ot_1_5_premium"], st.session_state.language),
                "--" if not data["ot_2_0_premium"] else format_number(data["ot_2_0_premium"], st.session_state.language),
                "--" if not data["rate_1_5"] else format_number(data["rate_1_5"], st.session_state.language),
                "--" if not data["rate_2_0"] else format_number(data["rate_2_0"], st.session_state.language),
                format_number(data['deduction_limit'], st.session_state.language),
                data["method_used"],
                "--" if not data["over_40"] else data["over_40"],
                "--" if not data["ot_1_5x"] else data["ot_1_5x"],
                "--" if not data["filing_status"] else data["filing_status"],
                "--" if not data["ss_check"] else data["ss_check"],
                "--" if not data["itin_check"] else data["itin_check"],
            ]
        }
        st.dataframe(pd.DataFrame(data_summary), width='stretch')

# ────────────────────────────────────────────────
# DESCARGA DE REPORTE PDF – CORRECTED VERSION
# ────────────────────────────────────────────────
def build_final_pdf(user_name, uploaded_files, num_docs, results, lang):
    import os

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    font_regular = os.path.join(BASE_DIR, "fonts", "DejaVuSans.ttf")
    font_bold    = os.path.join(BASE_DIR, "fonts", "DejaVuSans-Bold.ttf")

    # ── Page setup ──
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 20, 20)

    pdf.add_font("DejaVu", "",  font_regular)
    pdf.add_font("DejaVu", "B", font_bold)
    pdf.set_font("DejaVu", "", 11)

    USABLE_W  = 170
    LABEL_W   = 120
    VALUE_W   = 50
    ROW_H     = 7
    ALT_COLOR = (245, 245, 245)
    INDENT    = 2   # mm padding instead of space characters

    # ── Helpers ──────────────────────────────────────────────────────────────

    def section_title(text):
        pdf.ln(8)
        pdf.set_fill_color(30, 100, 200)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("DejaVu", "B", 12)
        pdf.set_x(pdf.l_margin + INDENT)
        pdf.cell(USABLE_W - INDENT, 9, text, new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("DejaVu", "", 11)
        pdf.ln(2)

    def table_row(label, value, row_index=0):
        x = pdf.get_x()
        y = pdf.get_y()

        # Estimate row height based on label length
        avg_char_w = pdf.get_string_width("a")
        chars_per_line = int((LABEL_W - INDENT) / max(avg_char_w, 1))
        lines_needed = max(1, -(-len(label) // chars_per_line))  # ceiling div
        row_height = max(ROW_H, lines_needed * ROW_H)

        # Draw alternating background
        pdf.set_fill_color(*(ALT_COLOR if row_index % 2 == 0 else (255, 255, 255)))
        pdf.rect(x, y, USABLE_W, row_height, style="F")

        # Label (bold, with precise indent)
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_xy(x + INDENT, y)
        pdf.multi_cell(LABEL_W - INDENT, ROW_H, label, border=0)

        # Value (regular, right-aligned)
        pdf.set_font("DejaVu", "", 10)
        pdf.set_xy(x + LABEL_W, y)
        pdf.multi_cell(VALUE_W, ROW_H, value, border=0, align="R")

        pdf.set_xy(x, y + row_height)

    def header_row(col1, col2):
        pdf.set_fill_color(50, 50, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("DejaVu", "B", 10)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.set_xy(x + INDENT, y)
        pdf.multi_cell(LABEL_W - INDENT, ROW_H + 1, col1, fill=True, border=0)
        pdf.set_xy(x + LABEL_W, y)
        pdf.multi_cell(VALUE_W, ROW_H + 1, col2, fill=True, border=0, align="R",
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("DejaVu", "", 10)

    def body_text(text, size=10):
        pdf.set_font("DejaVu", "", size)
        pdf.multi_cell(USABLE_W, 6, text)
        pdf.ln(2)

    def kv_simple(label, value, label_w=70):
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.set_font("DejaVu", "B", 11)
        pdf.multi_cell(label_w, 7, label, border=0)
        y_after_label = pdf.get_y()
        pdf.set_xy(x + label_w, y)
        pdf.set_font("DejaVu", "", 11)
        pdf.multi_cell(USABLE_W - label_w, 7, value, border=0)
        pdf.set_y(max(y_after_label, pdf.get_y()))

    # ── PAGE 1 — DISCLAIMER ──────────────────────────────────────────────────
    pdf.add_page()

    pdf.set_fill_color(200, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVu", "B", 14)
    pdf.set_x(pdf.l_margin + INDENT)
    pdf.cell(USABLE_W - INDENT, 12, t["disclaimer_label"],
             new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)
    body_text(t["disclaimer_msg"])

    # ── PAGE 2 — REPORT ──────────────────────────────────────────────────────
    pdf.add_page()

    # Title block
    pdf.set_fill_color(30, 100, 200)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVu", "B", 15)
    pdf.multi_cell(USABLE_W, 11, t["pdf_title"], align="C", fill=True,
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    pdf.set_font("DejaVu", "", 10)
    pdf.cell(USABLE_W, 6, t["pdf_generated_by"], align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(USABLE_W, 6,
             t["pdf_date"].format(datetime.now().strftime("%Y-%m-%d %H:%M")),
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Taxpayer info box — measure first, draw background, then render text on top
    info_y = pdf.get_y()
    pdf.set_font("DejaVu", "B", 11)
    kv_simple(t["pdf_user_name"].replace("{}", "").strip(),  user_name)
    kv_simple(t["pdf_used_count"].replace("{}", "").strip(), str(num_docs))
    info_bottom = pdf.get_y()

    # Re-render with background
    pdf.set_y(info_y)
    pdf.set_fill_color(240, 244, 255)
    pdf.rect(pdf.get_x(), info_y, USABLE_W, info_bottom - info_y + 3, style="F")
    kv_simple(t["pdf_user_name"].replace("{}", "").strip(),  user_name)
    kv_simple(t["pdf_used_count"].replace("{}", "").strip(), str(num_docs))
    pdf.ln(4)

    # ── DATA SUMMARY TABLE ───────────────────────────────────────────────────
    section_title(t["pdf_summary_title"])
    header_row(t["data_column_concept"], t["data_column_value"])

    summary_items = [
        (t["data_concepts"][0],  format_number(results["total_income"],    lang=lang)),
        (t["data_concepts"][1],  format_number(results["base_salary"],     lang=lang)),
        (t["data_concepts"][2],  format_number(results["ot_1_5_total"],    lang=lang)),
        (t["data_concepts"][3],  format_number(results["ot_2_0_total"],    lang=lang)),
        (t["data_concepts"][4],  format_number(results["ot_total_paid"],   lang=lang)),
        (t["data_concepts"][5],  format_number(results["ot_1_5_premium"],  lang=lang)),
        (t["data_concepts"][6],  format_number(results["ot_2_0_premium"],  lang=lang)),
        (t["data_concepts"][7],  format_number(results["rate_1_5"],        lang=lang)),
        (t["data_concepts"][8],  format_number(results["rate_2_0"],        lang=lang)),
        (t["data_concepts"][9],  format_number(results["deduction_limit"], lang=lang)),
        (t["data_concepts"][10], results["method_used"]),
        (t["data_concepts"][11], results["over_40"]),
        (t["data_concepts"][12], results["ot_1_5x"]),
        (t["data_concepts"][13], results["filing_status"]),
        (t["data_concepts"][14], results["ss_check"]),
        (t["data_concepts"][15], results["itin_check"]),
    ]

    for i, (label, value) in enumerate(summary_items):
        table_row(label, value, row_index=i)

    # ── RESULTS TABLE ────────────────────────────────────────────────────────
    section_title(t["pdf_results_title"])
    header_row(t["data_column_concept"], t["data_column_value"])

    results_items = [
        (t["qoc_gross_label"],       format_number(results["qoc_gross"],       lang=lang)),
        (t["phaseout_limit_label"],  format_number(results["deduction_limit"], lang=lang)),
        (t["total_deduction_label"], format_number(results["total_deduction"], lang=lang)),
    ]
    for i, (label, value) in enumerate(results_items):
        table_row(label, value, row_index=i)

    # Final deduction highlight box
    pdf.ln(8)
    pdf.set_fill_color(0, 140, 60)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVu", "B", 13)
    pdf.set_x(pdf.l_margin + INDENT)
    pdf.multi_cell(
        USABLE_W - INDENT, 13,
        t["pdf_final_deduction"].format(format_number(results["total_deduction"], lang=lang)),
        fill=True, new_x="LMARGIN", new_y="NEXT"
    )
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", "", 11)

    # ── EVIDENCE SECTION ─────────────────────────────────────────────────────
    section_title(t["pdf_evidence_title"])
    if uploaded_files:
        body_text(t["pdf_docs_attached"].format(len(uploaded_files)))
    else:
        body_text(t["pdf_no_docs"])

    # ── MERGE WITH ATTACHMENTS ───────────────────────────────────────────────
    pdf_bytes = pdf.output()
    merger = PdfMerger()
    merger.append(BytesIO(pdf_bytes))

    if uploaded_files:
        for uploaded_file in uploaded_files:
            merger.append(BytesIO(uploaded_file.read()))

    final_io = BytesIO()
    merger.write(final_io)
    merger.close()

    return final_io.getvalue()

if eligible and st.session_state.results:
    st.subheader(t["download_section_title"])

    user_name = st.text_input(
        t["download_name_label"],
        placeholder=t["download_name_placeholder"],
        key="pdf_user_name_input"
    )

    uploaded_files = st.file_uploader(
        t["download_docs_label"],
        type=["pdf"],
        accept_multiple_files=True,
        help=t["download_docs_help"],
        key="pdf_upload"
    )
    num_docs = len(uploaded_files) if uploaded_files else 0

    col_gen, col_space = st.columns([1, 3])  # para alinear mejor

    with col_gen:
        # Botón GENERAR (solo aparece si NO se ha generado aún)
        if st.session_state.pdf_bytes is None:
            if st.button(t["generate_pdf"], type="primary", disabled=not user_name.strip(), width="stretch"):
                if not user_name.strip():
                    st.error("pdf_missing_name")
                else:
                    with st.spinner(t["spinner_generating_pdf"]):
                        try:
                            pdf_bytes = build_final_pdf(
                                user_name=user_name,
                                uploaded_files=uploaded_files,
                                num_docs=num_docs,
                                results=st.session_state.results,
                                lang=st.session_state.language
                            )
                            st.session_state.pdf_bytes = pdf_bytes
                            st.rerun()  # importante para que desaparezca el botón Generar
                        except Exception as e:
                            st.error(t["error_pdf_generation"].format(str(e)))

        # Botón DESCARGAR (solo aparece DESPUÉS de generar)
        if st.session_state.pdf_bytes is not None:
            st.success(t["generated_pdf_success"])
            st.info(t["generated_pdf_success_info"])
            st.download_button(
                label=t["download_button_now"],
                data=st.session_state.pdf_bytes,
                file_name=f"ZaiOT_Reporte_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
                key="pdf_download_final"
            )
        
# Footer
st.markdown("---")
st.caption(t["footer"].format(date=datetime.now().strftime("%Y-%m-%d")))