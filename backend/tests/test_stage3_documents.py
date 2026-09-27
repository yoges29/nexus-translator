import io
from PIL import Image
from pypdf import PdfWriter

from app.models.document import DocumentHistory
from app.services.providers.ocr import BoundingBox, OCRRegion, OCRResult


def _create_pdf_document(pages: int = 1, text: str = "Hello document translation") -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    for i in range(pages):
        story.append(Paragraph(f"{text} on page {i + 1}", styles["Normal"]))
        if i < pages - 1:
            story.append(PageBreak())
    doc.build(story)
    return buf.getvalue()


def _create_scanned_pdf(image_text: str = "Scanned text inside PDF") -> bytes:
    """Creates a PDF containing an embedded image simulating a scanned document."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Image as ReportLabImage

    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    story = [ReportLabImage(img_buf, width=200, height=60)]
    doc.build(story)
    return buf.getvalue()


def _create_password_pdf() -> bytes:
    """Creates a password-protected encrypted PDF."""
    raw = _create_pdf_document(1, "Confidential text")
    reader_buf = io.BytesIO(raw)
    from pypdf import PdfReader
    reader = PdfReader(reader_buf)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("secret123")
    out_buf = io.BytesIO()
    writer.write(out_buf)
    return out_buf.getvalue()


class AsyncMockDocOCR:
    def __init__(self, text: str = "Scanned OCR text"):
        self.text = text

    async def extract_text(self, image_bytes: bytes) -> str:
        return self.text

    async def process_image(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(
            text=self.text,
            language="en",
            regions=[OCRRegion(text=self.text, bounding_box=BoundingBox(10, 10, 100, 30))],
        )


# ============================================================================
# 1. TXT Document Tests
# ============================================================================


def test_txt_translate_success(client, mock_provider):
    txt_content = "First paragraph in English.\n\nSecond paragraph in English.".encode("utf-8")
    response = client.post(
        "/api/documents/txt/translate",
        files={"file": ("notes.txt", io.BytesIO(txt_content), "text/plain")},
        data={"target_language": "ta", "source_language": "en", "translation_style": "general"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "txt"
    assert data["target_language"] == "ta"
    assert data["status"] == "completed"
    assert "notes_ta.txt" in data["download_filename"]
    assert data["download_url"] is not None


def test_txt_translate_generic_endpoint(client, mock_provider):
    txt_content = b"Simple document to translate via generic route."
    response = client.post(
        "/api/documents/translate",
        files={"file": ("memo.txt", io.BytesIO(txt_content), "text/plain")},
        data={"target_language": "es", "source_language": "auto"},
    )
    assert response.status_code == 200
    assert response.json()["document_type"] == "txt"


def test_txt_translate_empty_file_error(client, mock_provider):
    response = client.post(
        "/api/documents/txt/translate",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        data={"target_language": "es"},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_txt_translate_wrong_extension_on_txt_endpoint(client, mock_provider):
    response = client.post(
        "/api/documents/txt/translate",
        files={"file": ("data.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"target_language": "es"},
    )
    assert response.status_code == 400
    assert "Only TXT documents (.txt) are supported" in response.json()["detail"]


def test_txt_oversized_file(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    orig_limit = settings.max_document_size_bytes
    settings.max_document_size_bytes = 200  # tiny limit
    try:
        big_bytes = b"A" * 600
        response = client.post(
            "/api/documents/txt/translate",
            files={"file": ("large.txt", io.BytesIO(big_bytes), "text/plain")},
            data={"target_language": "es"},
        )
        assert response.status_code == 413
    finally:
        settings.max_document_size_bytes = orig_limit


# ============================================================================
# 2. PDF Document Tests
# ============================================================================


def test_pdf_translate_single_page_success(client, mock_provider):
    pdf_bytes = _create_pdf_document(pages=1, text="The quick brown fox jumps over the lazy dog.")
    response = client.post(
        "/api/documents/pdf/translate",
        files={"file": ("sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"target_language": "ta", "source_language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "pdf"
    assert data["page_count"] == 1
    assert data["target_language"] == "ta"
    assert "sample_ta.pdf" in data["download_filename"]


def test_pdf_translate_multi_page_success(client, mock_provider):
    pdf_bytes = _create_pdf_document(pages=3, text="Multipage test document content")
    response = client.post(
        "/api/documents/translate",
        files={"file": ("multipage.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"target_language": "es", "source_language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "pdf"
    assert data["page_count"] == 3


def test_pdf_translate_corrupted_file(client, mock_provider):
    response = client.post(
        "/api/documents/pdf/translate",
        files={"file": ("corrupt.pdf", io.BytesIO(b"Not a real PDF"), "application/pdf")},
        data={"target_language": "es"},
    )
    assert response.status_code == 400
    assert "Invalid or corrupted PDF" in response.json()["detail"]


def test_pdf_translate_password_protected(client, mock_provider):
    encrypted_pdf = _create_password_pdf()
    response = client.post(
        "/api/documents/pdf/translate",
        files={"file": ("locked.pdf", io.BytesIO(encrypted_pdf), "application/pdf")},
        data={"target_language": "es"},
    )
    assert response.status_code == 400
    assert "Password-protected PDFs are not supported" in response.json()["detail"]


def test_pdf_translate_scanned_ocr_fallback(client, mock_provider, monkeypatch):
    mock_ocr = AsyncMockDocOCR(text="Scanned text recognized by OCR")
    monkeypatch.setattr("app.services.document_service.get_ocr_provider", lambda: mock_ocr)

    scanned_pdf = _create_scanned_pdf()
    response = client.post(
        "/api/documents/pdf/translate",
        files={"file": ("scanned.pdf", io.BytesIO(scanned_pdf), "application/pdf")},
        data={"target_language": "ta", "source_language": "auto"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "pdf"
    assert data["status"] == "completed"


def test_pdf_translate_no_readable_text_error(client, mock_provider, monkeypatch):
    empty_ocr = AsyncMockDocOCR(text="")
    monkeypatch.setattr("app.services.document_service.get_ocr_provider", lambda: empty_ocr)

    scanned_pdf = _create_scanned_pdf()
    response = client.post(
        "/api/documents/pdf/translate",
        files={"file": ("empty_scanned.pdf", io.BytesIO(scanned_pdf), "application/pdf")},
        data={"target_language": "ta"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "No readable text was found in this PDF."


# ============================================================================
# 3. Download, Delete, and Path Traversal Security
# ============================================================================


def test_document_download_and_delete_lifecycle(client, mock_provider):
    txt_content = b"Content to test download and delete lifecycle."
    upload_res = client.post(
        "/api/documents/translate",
        files={"file": ("lifecycle.txt", io.BytesIO(txt_content), "text/plain")},
        data={"target_language": "ta", "source_language": "en"},
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["id"]

    # 1. Download
    down_res = client.get(f"/api/documents/{doc_id}/download")
    assert down_res.status_code == 200
    assert "Content-Disposition" in down_res.headers
    assert len(down_res.content) > 0

    # 2. List
    list_res = client.get("/api/documents")
    assert list_res.status_code == 200
    doc_ids = [d["id"] for d in list_res.json()["items"]]
    assert doc_id in doc_ids

    # 3. Delete
    del_res = client.delete(f"/api/documents/{doc_id}")
    assert del_res.status_code == 204

    # 4. Verify gone
    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.status_code == 404


def test_document_path_traversal_sanitization(client, mock_provider, db_session):
    # Attempting to upload with path traversal in filename
    txt_content = b"Path traversal attempt content."
    res = client.post(
        "/api/documents/translate",
        files={"file": ("../../../../etc/shadow.txt", io.BytesIO(txt_content), "text/plain")},
        data={"target_language": "ta", "source_language": "en"},
    )
    assert res.status_code == 200
    doc_id = res.json()["id"]

    record = db_session.get(DocumentHistory, doc_id)
    assert ".." not in record.download_filename
    assert record.filename == "____etc_shadow.txt" or "shadow.txt" in record.filename


def test_document_download_path_traversal_blocked(client, db_session):
    # If a document record maliciously points outside storage root
    record = DocumentHistory(
        filename="hack.txt",
        document_type="txt",
        file_size=10,
        source_language="en",
        target_language="ta",
        page_count=1,
        original_text_sample="test",
        translated_text_sample="test",
        status="completed",
        download_filename="hack.txt",
        output_path="C:/Windows/System32/drivers/etc/hosts",
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)

    res = client.get(f"/api/documents/{record.id}/download")
    assert res.status_code in (403, 404)
