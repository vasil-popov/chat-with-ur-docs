import base64
import json
import logging
import os
import re

logger = logging.getLogger(__name__)


def _get_llm():
    from app.deps.dependency_container import di_container_instance
    return di_container_instance.llm_client


def _ocr_with_llm(image_bytes: bytes, mime: str, prompt: str) -> str:
    from langchain_core.messages import HumanMessage
    b64 = base64.b64encode(image_bytes).decode()
    llm = _get_llm()
    msg = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        {"type": "text", "text": prompt},
    ])
    response = llm.invoke([msg])
    content = response.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and "text" in b]
        return "\n".join(parts).strip()
    return str(content).strip()


def extract_text(file_path: str, file_type: str, mime_type: str) -> str:
    if file_type == "image":
        return _extract_image(file_path, mime_type)
    elif file_type == "pdf":
        return _extract_pdf(file_path)
    elif file_type == "txt":
        return _extract_txt(file_path)
    elif file_type == "excel":
        return _extract_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def _extract_image(path: str, mime_type: str) -> str:
    with open(path, "rb") as f:
        image_bytes = f.read()
    return _ocr_with_llm(
        image_bytes,
        mime_type,
        "Extract all text from this image. If it is a receipt or invoice, include every line item, "
        "price, subtotal, tax, and total. Return only the extracted text, no commentary.",
    )


def _extract_pdf(path: str) -> str:
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    text_parts = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(text_parts).strip()

    if len(text) < 50:
        # Scanned PDF — render first page and OCR it
        doc = fitz.open(path)
        pix = doc[0].get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        doc.close()
        text = _ocr_with_llm(img_bytes, "image/png", "Extract all text from this scanned document page. Return only the extracted text.")

    return text


def _extract_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _extract_excel(path: str) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    parts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        parts.append(f"## Sheet: {sheet_name}")
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [str(c) if c is not None else "" for c in rows[0]]
        parts.append("| " + " | ".join(headers) + " |")
        parts.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows[1:]:
            cells = [str(c) if c is not None else "" for c in row]
            parts.append("| " + " | ".join(cells) + " |")
    wb.close()
    return "\n".join(parts)


def is_receipt(text: str) -> bool:
    keywords = [
        # English
        "total", "subtotal", "sub-total", "tax", "amount due", "receipt", "invoice",
        "payment", "cash", "change", "qty", "quantity",
        # Bulgarian
        "обща сума", "фискален", "бон", "сума", "общо", "ддс", "каса",
        "касова", "плащане", "ресто", "брой", "артикул",
        # Currency symbols / codes (strong signal on their own)
        "лв.", " лв", "bgn", "eur", "usd",
    ]
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw in text_lower)
    # Match prices with period or comma as decimal separator (e.g. 2.07 or 2,07)
    has_price = bool(re.search(r"\d+[.,]\d{2}", text))
    return hits >= 2 and has_price


def parse_receipt_items(text: str, llm) -> list[dict]:
    from langchain_core.messages import HumanMessage

    today_str = __import__("datetime").date.today().isoformat()
    prompt = f"""Extract every line item from this receipt text. Return a JSON array (and nothing else) where each element has:
  "description": string,
  "amount": number (positive, in the currency shown),
  "category": one of ["Food", "Shopping", "Transport", "Health", "Entertainment", "Other"],
  "transaction_date": "{today_str}"

Receipt text:
{text}

JSON array:"""

    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content
    if isinstance(content, list):
        content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and "text" in b)
    raw = content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        items = json.loads(raw)
        return [i for i in items if isinstance(i.get("amount"), (int, float)) and i["amount"] > 0]
    except json.JSONDecodeError:
        logger.warning("Failed to parse receipt JSON: %s", raw[:200])
        return []
