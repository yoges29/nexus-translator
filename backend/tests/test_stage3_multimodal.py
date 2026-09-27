import io
from PIL import Image

from app.services.providers.ocr import OCRRegion, BoundingBox


def _create_test_image(format="PNG", text_content="hello", size=(200, 100)) -> bytes:
    img = Image.new("RGB", size, color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def _create_test_docx(text="Hello world paragraph") -> bytes:
    import docx

    doc = docx.Document()
    doc.add_heading("Test Heading", level=1)
    doc.add_paragraph(text)
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Cell 1"
    table.rows[0].cells[1].text = "Cell 2"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _create_test_pdf(pages=1, text="Hello world PDF content") -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import Paragraph, SimpleDocTemplate, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet

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


# ============================================================================
# 1. OCR & Image Translation Tests
# ============================================================================


def test_ocr_extract_success(client, mock_provider, monkeypatch):
    from app.services import provider_factory

    mock_ocr = type(
        "MockOCR",
        (),
        {
            "process_image": lambda self, b: type(
                "Res",
                (),
                {
                    "text": "Hello world OCR",
                    "language": "en",
                    "regions": [
                        OCRRegion(
                            text="Hello",
                            bounding_box=BoundingBox(x=10, y=10, width=50, height=20),
                            confidence=0.99,
                        )
                    ],
                },
            )()
        },
    )()
    monkeypatch.setattr(provider_factory, "get_ocr_provider", lambda: mock_ocr)
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _create_test_image("PNG")
    response = client.post(
        "/api/ocr/extract",
        files={"image": ("sample.png", io.BytesIO(img_bytes), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Hello world OCR"
    assert data["language"] == "en"
    assert len(data["regions"]) == 1
    assert data["regions"][0]["bounding_box"]["x"] == 10


def test_ocr_extract_unsupported_format(client, mock_provider):
    response = client.post(
        "/api/ocr/extract",
        files={"image": ("test.exe", io.BytesIO(b"fake binary"), "application/x-msdownload")},
    )
    assert response.status_code == 400
    assert "Unsupported image format" in response.json()["detail"] or "Unsupported" in response.json()["detail"]


def test_image_translate_success(client, mock_provider, monkeypatch):
    from app.services import provider_factory

    mock_ocr = type(
        "MockOCR",
        (),
        {
            "process_image": lambda self, b: type(
                "Res",
                (),
                {
                    "text": "Hello world",
                    "language": "en",
                    "regions": [],
                },
            )()
        },
    )()
    monkeypatch.setattr(provider_factory, "get_ocr_provider", lambda: mock_ocr)
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: mock_ocr)

    img_bytes = _create_test_image("JPEG")
    response = client.post(
        "/api/image/translate",
        files={"file": ("sample.jpg", io.BytesIO(img_bytes), "image/jpeg")},
        data={"target_language": "ta", "source_language": "en", "translation_style": "general"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_language"] == "ta"
    assert data["extracted_text"] == "Hello world"
    assert "translated_text" in data
    assert data["history_id"] is not None


def test_image_translate_no_text_detected(client, mock_provider, monkeypatch):
    from app.services import provider_factory

    empty_ocr = type(
        "MockEmptyOCR",
        (),
        {
            "process_image": lambda self, b: type(
                "Res",
                (),
                {
                    "text": "",
                    "language": None,
                    "regions": [],
                },
            )()
        },
    )()
    monkeypatch.setattr(provider_factory, "get_ocr_provider", lambda: empty_ocr)
    monkeypatch.setattr("app.services.translation_service.get_ocr_provider", lambda: empty_ocr)

    img_bytes = _create_test_image("PNG")
    response = client.post(
        "/api/image/translate",
        files={"file": ("empty.png", io.BytesIO(img_bytes), "image/png")},
        data={"target_language": "ta"},
    )
    assert response.status_code == 400
    assert "No text was detected" in response.json()["detail"]


def test_image_oversized_payload(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    original_size = settings.max_image_size_bytes
    settings.max_image_size_bytes = 100  # tiny limit
    try:
        big_bytes = b"X" * 500
        response = client.post(
            "/api/image/translate",
            files={"file": ("big.png", io.BytesIO(big_bytes), "image/png")},
            data={"target_language": "ta"},
        )
        assert response.status_code == 413
    finally:
        settings.max_image_size_bytes = original_size


# ============================================================================
# 2. Document Translation Tests (TXT, DOCX, PDF)
# ============================================================================


def test_document_translate_txt_success(client, mock_provider):
    txt_content = b"This is a test document to translate.\nSecond line of the document."
    response = client.post(
        "/api/documents/translate",
        files={"file": ("sample.txt", io.BytesIO(txt_content), "text/plain")},
        data={"target_language": "ta", "source_language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "txt"
    assert data["target_language"] == "ta"
    assert data["status"] == "completed"
    assert "download_url" in data
    doc_id = data["id"]

    # Verify download endpoint
    dl_response = client.get(f"/api/documents/{doc_id}/download")
    assert dl_response.status_code == 200
    assert "attachment" in dl_response.headers.get("content-disposition", "")
    assert len(dl_response.content) > 0


def test_document_translate_docx_success(client, mock_provider):
    docx_bytes = _create_test_docx("Testing DOCX document translation.")
    response = client.post(
        "/api/documents/translate",
        files={"file": ("test_doc.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"target_language": "ta", "source_language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "docx"
    assert data["status"] == "completed"

    doc_id = data["id"]
    dl = client.get(f"/api/documents/{doc_id}/download")
    assert dl.status_code == 200
    assert len(dl.content) > 0


def test_document_translate_pdf_success(client, mock_provider):
    pdf_bytes = _create_test_pdf(pages=2, text="Report page content")
    response = client.post(
        "/api/documents/translate",
        files={"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"target_language": "ta", "source_language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "pdf"
    assert data["page_count"] == 2
    assert data["status"] == "completed"

    doc_id = data["id"]
    dl = client.get(f"/api/documents/{doc_id}/download")
    assert dl.status_code == 200
    assert len(dl.content) > 0


def test_document_translate_empty_file(client, mock_provider):
    response = client.post(
        "/api/documents/translate",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        data={"target_language": "ta"},
    )
    assert response.status_code == 400


def test_document_translate_unsupported_format(client, mock_provider):
    response = client.post(
        "/api/documents/translate",
        files={"file": ("script.py", io.BytesIO(b"print('hello')"), "text/x-python")},
        data={"target_language": "ta"},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_document_delete_lifecycle(client, mock_provider):
    txt_content = b"Content to delete"
    res = client.post(
        "/api/documents/translate",
        files={"file": ("delete_me.txt", io.BytesIO(txt_content), "text/plain")},
        data={"target_language": "ta", "source_language": "en"},
    )
    doc_id = res.json()["id"]

    del_res = client.delete(f"/api/documents/{doc_id}")
    assert del_res.status_code == 204

    # Verify not found
    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.status_code == 404


# ============================================================================
# 3. Conversation Mode Tests
# ============================================================================


def test_conversation_session_crud(client, mock_provider):
    # 1. Create Session
    create_res = client.post(
        "/api/conversations/sessions",
        json={"language_a": "ta", "language_b": "en", "title": "Tamil - English Test"},
    )
    assert create_res.status_code == 200
    session_data = create_res.json()
    session_id = session_data["id"]
    assert session_data["language_a"] == "ta"
    assert session_data["language_b"] == "en"

    # 2. Speaker A sends message (ta -> en)
    msg_a = client.post(
        f"/api/conversations/sessions/{session_id}/messages",
        json={"speaker": "speaker_a", "text": "வணக்கம்"},
    )
    assert msg_a.status_code == 200
    data_a = msg_a.json()
    assert data_a["source_language"] == "ta"
    assert data_a["target_language"] == "en"
    assert data_a["original_text"] == "வணக்கம்"

    # 3. Speaker B replies (en -> ta)
    msg_b = client.post(
        f"/api/conversations/sessions/{session_id}/messages",
        json={"speaker": "speaker_b", "text": "Hello, nice to meet you."},
    )
    assert msg_b.status_code == 200
    data_b = msg_b.json()
    assert data_b["source_language"] == "en"
    assert data_b["target_language"] == "ta"

    # 4. Get session with messages
    get_res = client.get(f"/api/conversations/sessions/{session_id}")
    assert get_res.status_code == 200
    assert len(get_res.json()["messages"]) == 2

    # 5. List sessions
    list_res = client.get("/api/conversations/sessions")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # 6. Delete session
    del_res = client.delete(f"/api/conversations/sessions/{session_id}")
    assert del_res.status_code == 204


def test_conversation_audio_message(client, mock_provider, mock_stt):
    create_res = client.post(
        "/api/conversations/sessions",
        json={"language_a": "en", "language_b": "ta"},
    )
    session_id = create_res.json()["id"]

    fake_wav = io.BytesIO(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    res = client.post(
        f"/api/conversations/sessions/{session_id}/messages/audio",
        files={"file": ("speech.wav", fake_wav, "audio/wav")},
        data={"speaker": "speaker_a"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["original_text"] == "Hello world speech"
    assert "translated_text" in data


# ============================================================================
# 4. Multimodal History Tests
# ============================================================================


def test_multimodal_history_filtering(client, mock_provider):
    # Perform a text translate
    client.post(
        "/api/translate",
        json={"source_language": "en", "target_language": "ta", "text": "Test history line", "input_method": "text"},
    )
    # Perform a document translate
    client.post(
        "/api/documents/translate",
        files={"file": ("history_test.txt", io.BytesIO(b"Document history content"), "text/plain")},
        data={"target_language": "ta", "source_language": "en"},
    )

    # 1. Fetch all
    res_all = client.get("/api/history/multimodal")
    assert res_all.status_code == 200
    modalities = [item["modality"] for item in res_all.json()["items"]]
    assert "text" in modalities
    assert "document" in modalities

    # 2. Filter by document
    res_doc = client.get("/api/history/multimodal?modality=document")
    assert res_doc.status_code == 200
    for item in res_doc.json()["items"]:
        assert item["modality"] == "document"

    # 3. Filter by text
    res_txt = client.get("/api/history/multimodal?modality=text")
    assert res_txt.status_code == 200
    for item in res_txt.json()["items"]:
        assert item["modality"] == "text"


# ============================================================================
# 5. Security & Path Traversal Tests
# ============================================================================


def test_security_path_traversal_sanitization(client, mock_provider):
    traversal_name = "../../../etc/passwd.txt"
    res = client.post(
        "/api/documents/translate",
        files={"file": (traversal_name, io.BytesIO(b"Safe content"), "text/plain")},
        data={"target_language": "ta", "source_language": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    # Check that filename doesn't contain path traversal components
    assert ".." not in data["filename"]
    assert "/" not in data["filename"]
    assert "\\" not in data["filename"]
