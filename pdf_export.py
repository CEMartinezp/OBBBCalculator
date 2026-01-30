from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import io

def generate_pdf(total, tips, ot) -> bytes:
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    content = [
        Paragraph("OBBB Deduction Summary", styles["Title"]),
        Paragraph(f"<b>Total Deduction:</b> ${total:,.0f}", styles["Normal"]),
        Paragraph(f"<b>Tips Deduction:</b> ${tips:,.0f}", styles["Normal"]),
        Paragraph(f"<b>Overtime Deduction:</b> ${ot:,.0f}", styles["Normal"]),
    ]

    doc.build(content)

    buffer.seek(0)
    return buffer.read()
