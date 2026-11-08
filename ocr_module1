from __future__ import annotations
from pathlib import Path

def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        import pdfplumber
        text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text)
    except Exception:
        return ""

def extract_text_from_image(image_path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(image_path))
    except Exception:
        return ""
