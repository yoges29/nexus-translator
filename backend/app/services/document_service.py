import inspect
import io
import logging
import os
import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ProviderError
from app.core.languages import is_translation_supported
from app.models.document import DocumentHistory
from app.services.detector import LanguageDetector
from app.services.provider_factory import get_ocr_provider, get_translation_provider

logger = logging.getLogger("nexus.translator.document")

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "application/octet-stream",  # often sent by browsers for .docx or .txt
}


def _sanitize_filename(filename: str) -> str:
    cleaned = Path(filename).name
    cleaned = re.sub(r"[^\w\s\.-]", "_", cleaned)
    return cleaned.strip() or "document"


class DocumentTranslationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.translation_provider = get_translation_provider()
        self.ocr_provider = get_ocr_provider()

    def _validate_file_meta(self, filename: str, content_type: str, file_size: int) -> tuple[str, str]:
        if file_size <= 0:
            raise AppError("Uploaded document is empty.")
        if file_size > self.settings.max_document_size_bytes:
            max_mb = self.settings.max_document_size_bytes // (1024 * 1024)
            raise AppError(f"Document exceeds maximum size limit of {max_mb}MB.", status_code=413)

        safe_name = _sanitize_filename(filename)
        ext = Path(safe_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise AppError(f"Unsupported file format '{ext}'. Supported formats: PDF, DOCX, TXT.")

        return safe_name, ext

    async def _translate_text_chunked(
        self, text: str, source_lang: str, target_lang: str, style: str = "general", chunk_size: int = 1500
    ) -> str:
        paragraphs = text.split("\n")
        translated_paragraphs = []
        current_chunk = []
        current_len = 0

        async def flush_chunk():
            nonlocal current_chunk, current_len
            if not current_chunk:
                return
            combined = "\n".join(current_chunk)
            translated = await self.translation_provider.translate(
                combined, source_lang, target_lang, style=style
            )
            translated_paragraphs.append(translated)
            current_chunk = []
            current_len = 0

        for para in paragraphs:
            if not para.strip():
                if current_chunk:
                    await flush_chunk()
                translated_paragraphs.append("")
                continue

            if current_len + len(para) > chunk_size and current_chunk:
                await flush_chunk()

            current_chunk.append(para)
            current_len += len(para)

        if current_chunk:
            await flush_chunk()

        return "\n".join(translated_paragraphs)

    async def process_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        target_language: str,
        source_language: str = "auto",
        translation_style: str = "general",
        user_id: int | None = None,
    ) -> DocumentHistory:
        safe_name, ext = self._validate_file_meta(filename, content_type, len(file_bytes))
        target_lang = target_language.strip().lower()
        source_lang = source_language.strip().lower()

        if not is_translation_supported(target_lang):
            raise AppError(f"Unsupported target language: {target_lang}")
        if source_lang != "auto" and not is_translation_supported(source_lang):
            raise AppError(f"Unsupported source language: {source_lang}")

        doc_type = ext.lstrip(".")

        if doc_type == "txt":
            return await self._process_txt(
                file_bytes, safe_name, target_lang, source_lang, translation_style, user_id
            )
        elif doc_type == "docx":
            return await self._process_docx(
                file_bytes, safe_name, target_lang, source_lang, translation_style, user_id
            )
        elif doc_type == "pdf":
            return await self._process_pdf(
                file_bytes, safe_name, target_lang, source_lang, translation_style, user_id
            )
        else:
            raise AppError(f"Unsupported document type: {doc_type}")

    async def _process_txt(
        self,
        file_bytes: bytes,
        filename: str,
        target_lang: str,
        source_lang: str,
        style: str,
        user_id: int | None,
    ) -> DocumentHistory:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode("latin-1")
            except Exception as exc:
                raise AppError("Unable to decode text file. Ensure it is encoded in UTF-8 or ASCII.") from exc

        text = text.strip()
        if not text:
            raise AppError("Text document contains no content.")

        # Resolve source language
        resolved_source = source_lang
        if resolved_source == "auto":
            det = LanguageDetector.detect(text[:500])
            resolved_source = det.language
            if not is_translation_supported(resolved_source):
                resolved_source = "en"

        if resolved_source == target_lang:
            raise AppError("Source and target languages must be different.")

        translated_text = await self._translate_text_chunked(
            text, resolved_source, target_lang, style=style
        )

        stem = Path(filename).stem
        download_name = f"{stem}_{target_lang}.txt"
        unique_file = f"{uuid.uuid4().hex}_{download_name}"
        out_path = self.settings.storage_path / unique_file
        out_path.write_text(translated_text, encoding="utf-8")

        record = DocumentHistory(
            user_id=user_id,
            filename=filename,
            document_type="txt",
            file_size=len(file_bytes),
            source_language=resolved_source,
            target_language=target_lang,
            page_count=1,
            original_text_sample=text[:500],
            translated_text_sample=translated_text[:500],
            status="completed",
            download_filename=download_name,
            output_path=str(out_path),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    async def _process_docx(
        self,
        file_bytes: bytes,
        filename: str,
        target_lang: str,
        source_lang: str,
        style: str,
        user_id: int | None,
    ) -> DocumentHistory:
        try:
            import docx
        except ImportError as exc:
            raise ProviderError("python-docx is not installed.") from exc

        try:
            doc = docx.Document(io.BytesIO(file_bytes))
        except Exception as exc:
            raise AppError("Invalid or corrupted DOCX file.") from exc

        # Extract all paragraph texts and table cell texts
        all_texts = []
        for p in doc.paragraphs:
            if p.text.strip():
                all_texts.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        all_texts.append(cell.text)

        full_extracted = "\n".join(all_texts).strip()
        if not full_extracted:
            raise AppError("DOCX document contains no readable text.")

        resolved_source = source_lang
        if resolved_source == "auto":
            det = LanguageDetector.detect(full_extracted[:500])
            resolved_source = det.language
            if not is_translation_supported(resolved_source):
                resolved_source = "en"

        if resolved_source == target_lang:
            raise AppError("Source and target languages must be different.")

        # Translate in-place while preserving styles and tables
        # Translate paragraphs
        for p in doc.paragraphs:
            if p.text.strip():
                try:
                    res = self.translation_provider.translate(
                        p.text, resolved_source, target_lang, style=style
                    )
                    if inspect.isawaitable(res):
                        res = await res
                    p.text = res
                except Exception as exc:
                    logger.warning("Paragraph translation error: %s", exc)

        # Translate tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for cp in cell.paragraphs:
                        if cp.text.strip():
                            try:
                                res = self.translation_provider.translate(
                                    cp.text, resolved_source, target_lang, style=style
                                )
                                if inspect.isawaitable(res):
                                    res = await res
                                cp.text = res
                            except Exception as exc:
                                logger.warning("Table cell translation error: %s", exc)

        # Translate headers and footers if present
        for section in doc.sections:
            try:
                for hp in section.header.paragraphs:
                    if hp.text.strip():
                        res = self.translation_provider.translate(
                            hp.text, resolved_source, target_lang, style=style
                        )
                        if inspect.isawaitable(res):
                            res = await res
                        hp.text = res
            except Exception:
                pass
            try:
                for fp in section.footer.paragraphs:
                    if fp.text.strip():
                        res = self.translation_provider.translate(
                            fp.text, resolved_source, target_lang, style=style
                        )
                        if inspect.isawaitable(res):
                            res = await res
                        fp.text = res
            except Exception:
                pass

        stem = Path(filename).stem
        download_name = f"{stem}_{target_lang}.docx"
        unique_file = f"{uuid.uuid4().hex}_{download_name}"
        out_path = self.settings.storage_path / unique_file
        doc.save(str(out_path))

        # Sample for preview
        preview_trans = "\n".join([p.text for p in doc.paragraphs if p.text.strip()][:5])

        record = DocumentHistory(
            user_id=user_id,
            filename=filename,
            document_type="docx",
            file_size=len(file_bytes),
            source_language=resolved_source,
            target_language=target_lang,
            page_count=max(1, len(doc.paragraphs) // 15),
            original_text_sample=full_extracted[:500],
            translated_text_sample=preview_trans[:500],
            status="completed",
            download_filename=download_name,
            output_path=str(out_path),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    async def _process_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        target_lang: str,
        source_lang: str,
        style: str,
        user_id: int | None,
    ) -> DocumentHistory:
        try:
            import pypdf
        except ImportError as exc:
            raise ProviderError("pypdf is not installed.") from exc

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        except Exception as exc:
            raise AppError("Invalid or corrupted PDF file.") from exc

        if reader.is_encrypted:
            raise AppError("Password-protected PDFs are not supported. Please decrypt the file and try again.")

        page_count = len(reader.pages)
        if page_count == 0:
            raise AppError("PDF document is empty (0 pages).")
        if page_count > self.settings.max_document_pages:
            raise AppError(
                f"PDF exceeds the maximum limit of {self.settings.max_document_pages} pages (has {page_count} pages)."
            )

        extracted_pages: list[str] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            extracted_pages.append(text)

        full_extracted = "\n".join(extracted_pages).strip()

        # Handle scanned PDF with OCR if text is virtually empty
        if len(full_extracted) < 15:
            logger.info("PDF has minimal extractable text. Attempting image OCR on pages...")
            ocr_texts: list[str] = []
            for page in reader.pages:
                for img_file in page.images:
                    try:
                        raw_res = self.ocr_provider.extract_text(img_file.data)
                        if inspect.isawaitable(raw_res):
                            res = await raw_res
                        else:
                            res = raw_res
                        if res and res.strip():
                            ocr_texts.append(res.strip())
                    except Exception as exc:
                        logger.warning("OCR on PDF image failed: %s", exc)

            if ocr_texts:
                full_extracted = "\n".join(ocr_texts).strip()

        if not full_extracted:
            raise AppError("No readable text was found in this PDF.")

        resolved_source = source_lang
        if resolved_source == "auto":
            det = LanguageDetector.detect(full_extracted[:500])
            resolved_source = det.language
            if not is_translation_supported(resolved_source):
                resolved_source = "en"

        if resolved_source == target_lang:
            raise AppError("Source and target languages must be different.")

        translated_text = await self._translate_text_chunked(
            full_extracted, resolved_source, target_lang, style=style
        )

        stem = Path(filename).stem
        download_name = f"{stem}_{target_lang}.pdf"
        unique_file = f"{uuid.uuid4().hex}_{download_name}"
        out_path = self.settings.storage_path / unique_file

        # Generate translated PDF using reportlab
        self._generate_pdf_document(translated_text, out_path, title=f"Translation: {filename}")

        record = DocumentHistory(
            user_id=user_id,
            filename=filename,
            document_type="pdf",
            file_size=len(file_bytes),
            source_language=resolved_source,
            target_language=target_lang,
            page_count=page_count,
            original_text_sample=full_extracted[:500],
            translated_text_sample=translated_text[:500],
            status="completed",
            download_filename=download_name,
            output_path=str(out_path),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _generate_pdf_document(self, text: str, output_path: Path, title: str = "Translation") -> None:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=letter,
                rightMargin=54,
                leftMargin=54,
                topMargin=54,
                bottomMargin=54,
            )
            styles = getSampleStyleSheet()
            title_style = styles["Heading1"]
            body_style = ParagraphStyle(
                "DocBody",
                parent=styles["Normal"],
                fontSize=11,
                leading=16,
                spaceAfter=10,
            )

            story = [
                Paragraph(title, title_style),
                Spacer(1, 0.2 * inch),
            ]

            paragraphs = text.split("\n")
            for para in paragraphs:
                cleaned = para.strip()
                if cleaned:
                    # Escape HTML entities for reportlab
                    escaped = cleaned.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Paragraph(escaped, body_style))
                else:
                    story.append(Spacer(1, 0.1 * inch))

            doc.build(story)
        except Exception as exc:
            logger.error("Failed to build PDF with reportlab: %s. Falling back to plain text file.", exc)
            output_path.write_text(text, encoding="utf-8")

    def get_document(self, doc_id: int) -> DocumentHistory:
        record = self.db.get(DocumentHistory, doc_id)
        if not record:
            raise AppError("Document not found.", status_code=404)
        return record

    def list_documents(self, user_id: int | None = None, limit: int = 50, offset: int = 0) -> tuple[list[DocumentHistory], int]:
        query = self.db.query(DocumentHistory)
        if user_id is not None:
            query = query.filter(DocumentHistory.user_id == user_id)
        total = query.count()
        items = query.order_by(DocumentHistory.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

    def delete_document(self, doc_id: int) -> None:
        record = self.get_document(doc_id)
        if record.output_path and os.path.exists(record.output_path):
            try:
                os.remove(record.output_path)
            except OSError as exc:
                logger.warning("Failed to delete physical file %s: %s", record.output_path, exc)
        self.db.delete(record)
        self.db.commit()
