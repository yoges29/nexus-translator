import io
import docx


def _create_docx_document(
    title: str = "Quarterly Business Report",
    paragraphs: list[str] | None = None,
    table_data: list[list[str]] | None = None,
    empty: bool = False,
) -> bytes:
    doc = docx.Document()
    if empty:
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    doc.add_heading(title, level=1)
    if paragraphs:
        for p in paragraphs:
            doc.add_paragraph(p)
    else:
        doc.add_paragraph("This is the executive summary of our global expansion strategy.")
        doc.add_paragraph("Revenue has grown significantly across all target markets.", style="List Bullet")

    if table_data:
        table = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
        for r_idx, row in enumerate(table_data):
            for c_idx, val in enumerate(row):
                table.cell(r_idx, c_idx).text = val
    else:
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Region"
        table.cell(0, 1).text = "Growth"
        table.cell(1, 0).text = "North America"
        table.cell(1, 1).text = "25%"

    # Add header and footer
    section = doc.sections[0]
    section.header.paragraphs[0].text = "Confidential Internal Memo"
    section.footer.paragraphs[0].text = "Page 1 of 1"

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ============================================================================
# 1. DOCX Translation Tests
# ============================================================================


def test_docx_translate_success(client, mock_provider):
    docx_bytes = _create_docx_document()
    response = client.post(
        "/api/documents/docx/translate",
        files={
            "file": (
                "annual_report.docx",
                io.BytesIO(docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"target_language": "fr", "source_language": "en", "translation_style": "formal"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "docx"
    assert data["target_language"] == "fr"
    assert data["source_language"] == "en"
    assert data["status"] == "completed"
    assert "annual_report_fr.docx" in data["download_filename"]
    assert data["download_url"] is not None
    assert "Quarterly Business Report" in data["original_text_sample"]

    # Verify download and inspect translated DOCX structure
    dl_resp = client.get(data["download_url"])
    assert dl_resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in dl_resp.headers["content-type"]

    translated_doc = docx.Document(io.BytesIO(dl_resp.content))
    # Check that headings and paragraphs exist and contain translation
    translated_texts = [p.text for p in translated_doc.paragraphs if p.text.strip()]
    assert len(translated_texts) >= 3
    # Our mock_provider returns "வணக்கம்"
    assert any("வணக்கம்" in t for t in translated_texts)

    # Check table translation
    assert len(translated_doc.tables) >= 1
    table = translated_doc.tables[0]
    cell_texts = [cell.text for row in table.rows for cell in row.cells]
    assert len(cell_texts) == 4
    assert all("வணக்கம்" in c for c in cell_texts)


def test_docx_translate_generic_endpoint(client, mock_provider):
    docx_bytes = _create_docx_document(
        title="Project Plan",
        paragraphs=["First milestone completed successfully.", "Next milestone scheduled for next quarter."],
    )
    response = client.post(
        "/api/documents/translate",
        files={
            "file": (
                "project_plan.docx",
                io.BytesIO(docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"target_language": "es", "source_language": "auto"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "docx"
    assert data["target_language"] == "es"
    assert data["status"] == "completed"


def test_docx_translate_auto_detect_language(client, mock_provider):
    docx_bytes = _create_docx_document(
        title="Bonjour le monde",
        paragraphs=["Ceci est un document en francais pour tester la detection automatique de la langue."],
    )
    response = client.post(
        "/api/documents/docx/translate",
        files={"file": ("french_memo.docx", io.BytesIO(docx_bytes), "application/octet-stream")},
        data={"target_language": "en", "source_language": "auto"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_language"] == "fr"
    assert data["target_language"] == "en"


def test_docx_translate_empty_document(client, mock_provider):
    docx_bytes = _create_docx_document(empty=True)
    response = client.post(
        "/api/documents/docx/translate",
        files={"file": ("empty.docx", io.BytesIO(docx_bytes), "application/octet-stream")},
        data={"target_language": "es"},
    )
    assert response.status_code == 400
    assert "DOCX document contains no readable text." in response.json()["detail"]


def test_docx_translate_corrupted_file(client, mock_provider):
    corrupted_bytes = b"PK\x03\x04this is totally corrupted and not a valid zip or docx file"
    response = client.post(
        "/api/documents/docx/translate",
        files={"file": ("broken.docx", io.BytesIO(corrupted_bytes), "application/octet-stream")},
        data={"target_language": "es"},
    )
    assert response.status_code == 400
    assert "Invalid or corrupted DOCX file." in response.json()["detail"]


def test_docx_translate_wrong_extension(client, mock_provider):
    txt_content = b"This is a text file, not a docx."
    response = client.post(
        "/api/documents/docx/translate",
        files={"file": ("document.txt", io.BytesIO(txt_content), "text/plain")},
        data={"target_language": "es"},
    )
    assert response.status_code == 400
    assert "Only DOCX documents (.docx) are supported at this endpoint." in response.json()["detail"]


def test_docx_translate_same_source_and_target(client, mock_provider):
    docx_bytes = _create_docx_document()
    response = client.post(
        "/api/documents/docx/translate",
        files={"file": ("memo.docx", io.BytesIO(docx_bytes), "application/octet-stream")},
        data={"target_language": "en", "source_language": "en"},
    )
    assert response.status_code == 400
    assert "Source and target languages must be different." in response.json()["detail"]


def test_docx_translate_unsupported_language(client, mock_provider):
    docx_bytes = _create_docx_document()
    response = client.post(
        "/api/documents/docx/translate",
        files={"file": ("memo.docx", io.BytesIO(docx_bytes), "application/octet-stream")},
        data={"target_language": "unsupported_lang_xyz"},
    )
    assert response.status_code == 400
    assert "Unsupported target language" in response.json()["detail"]


def test_docx_translate_file_too_large(client, mock_provider, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "max_document_size_bytes", 50)
    docx_bytes = _create_docx_document()
    response = client.post(
        "/api/documents/docx/translate",
        files={"file": ("huge.docx", io.BytesIO(docx_bytes), "application/octet-stream")},
        data={"target_language": "es"},
    )
    assert response.status_code == 413
    assert "Document exceeds maximum size limit" in response.json()["detail"]


def test_docx_history_multimodal_and_deletion(client, mock_provider):
    docx_bytes = _create_docx_document(
        title="Multimodal DOCX Check",
        paragraphs=["This doc will be tracked in multimodal history and then deleted."],
    )
    resp = client.post(
        "/api/documents/docx/translate",
        files={"file": ("multi_test.docx", io.BytesIO(docx_bytes), "application/octet-stream")},
        data={"target_language": "de", "source_language": "en"},
    )
    assert resp.status_code == 200
    doc_id = resp.json()["id"]

    # Check list documents
    list_resp = client.get("/api/documents")
    assert list_resp.status_code == 200
    doc_ids = [d["id"] for d in list_resp.json()["items"]]
    assert doc_id in doc_ids

    # Check multimodal history
    multi_resp = client.get("/api/history/multimodal?modality=document")
    assert multi_resp.status_code == 200
    multi_items = multi_resp.json()["items"]
    assert any(m["raw_id"] == doc_id and m["modality"] == "document" for m in multi_items)

    # Delete document
    del_resp = client.delete(f"/api/documents/{doc_id}")
    assert del_resp.status_code == 204

    # Subsequent get should 404
    assert client.get(f"/api/documents/{doc_id}").status_code == 404
    assert client.get(f"/api/documents/{doc_id}/download").status_code == 404
