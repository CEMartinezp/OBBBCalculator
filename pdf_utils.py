
import pdfplumber
import re

def extract_amounts(uploaded_files):
    magi = tips = ot = 0.0

    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages).upper()

            for _, amt in re.findall(r'(GROSS|YTD GROSS|BOX 1)[^\d]{0,20}\$?([\d,]+\.?\d*)', text):
                magi += float(amt.replace(",", ""))

            for _, amt in re.findall(r'(TIPS|ALLOCATED TIPS|BOX 7|BOX 8)[^\d]{0,20}\$?([\d,]+\.?\d*)', text):
                tips += float(amt.replace(",", ""))

            for _, amt in re.findall(r'(OVER[-\s]?TIME|OT)[^\d]{0,20}\$?([\d,]+\.?\d*)', text):
                ot += float(amt.replace(",", ""))

    return magi, tips, ot
