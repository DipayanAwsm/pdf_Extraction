import os
from typing import Tuple

import pdfplumber
from pdf2image import convert_from_path
import pytesseract


def _extract_text_native(pdf_path: str) -> str:
    extracted_pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            extracted_pages.append(text)
    return "\n".join(extracted_pages).strip()


def _extract_text_ocr(pdf_path: str, dpi: int = 300, lang: str = "eng") -> str:
    images = convert_from_path(pdf_path, dpi=dpi)
    ocr_pages = []
    for image in images:
        page_text = pytesseract.image_to_string(image, lang=lang)
        ocr_pages.append(page_text)
    return "\n".join(ocr_pages).strip()


def extract_text_from_pdf(pdf_path: str, use_ocr_fallback: bool = True, dpi: int = 300) -> Tuple[str, bool]:
    """
    Extract text from a PDF. Try native text first; optionally fall back to OCR.

    Returns (text, used_ocr).
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    text = _extract_text_native(pdf_path)
    used_ocr = False

    # Heuristic: if too little text or mostly whitespace, try OCR
    if use_ocr_fallback:
        normalized = (text or "").strip()
        if len(normalized) < 40:
            text = _extract_text_ocr(pdf_path, dpi=dpi)
            used_ocr = True

    return text, used_ocr



