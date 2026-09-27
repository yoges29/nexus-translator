import os
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.errors import AppError, ProviderError, raise_http_error
from app.core.languages import get_language_by_code, get_languages
from app.database.session import get_db

from app.schemas.conversation import (
    ConversationMessageItem,
    ConversationSessionItem,
    ConversationSessionListResponse,
    CreateSessionRequest,
    SendMessageRequest,
    UpdateSessionRequest,
)
from app.schemas.document import DocumentItem, DocumentListResponse
from app.schemas.ocr import ImageTranslateResponse, OCRExtractResponse
from app.schemas.translation import (
    AlternativesRequest,
    AlternativesResponse,
    DetectLanguageRequest,
    DetectLanguageResponse,
    HistoryItem,
    HistoryListResponse,
    LanguageItem,
    MultimodalHistoryItem,
    MultimodalHistoryResponse,
    OfflineStatusResponse,
    SynthesizeRequest,
    TranscribeResponse,
    TranslateRequest,
    TranslateResponse,
)

from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentTranslationService
from app.services.translation_service import TranslationService
from app.services.voice_service import VoiceTranslationService


router = APIRouter(prefix="/api", tags=["translation"])


@router.get("/languages", response_model=list[LanguageItem])
def list_languages() -> list[LanguageItem]:
    return [LanguageItem(**lang) for lang in get_languages()]


@router.get("/offline/status", response_model=OfflineStatusResponse)
def get_offline_status(db: Session = Depends(get_db)) -> OfflineStatusResponse:
    service = TranslationService(db)
    status = service.get_offline_status()
    return OfflineStatusResponse(**status)


@router.post("/translate", response_model=TranslateResponse)
async def translate(payload: TranslateRequest, db: Session = Depends(get_db)) -> TranslateResponse:
    service = TranslationService(db)
    try:
        source, target, translated, style, method, detected, history_id = await service.translate(
            payload.text,
            payload.source_language,
            payload.target_language,
            style=payload.translation_style,
            input_method=payload.input_method,
            mode=payload.mode,
        )
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)

    meta = service.get_last_translation_meta()

    return TranslateResponse(
        source_language=source,
        target_language=target,
        original_text=payload.text.strip(),
        translated_text=translated,
        translation_style=style,
        input_method=method,
        detected_language=detected,
        history_id=history_id,
        is_offline=bool(meta.get("is_offline", False) is True),
        provider_used=str(meta.get("provider_used", "online")),
    )





@router.post("/translate/alternatives", response_model=AlternativesResponse)
async def get_alternatives(payload: AlternativesRequest, db: Session = Depends(get_db)) -> AlternativesResponse:
    service = TranslationService(db)
    try:
        primary, alternatives = await service.get_alternatives(
            payload.text,
            payload.source_language,
            payload.target_language,
            style=payload.translation_style,
        )
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)

    return AlternativesResponse(
        primary=primary,
        alternatives=alternatives[:3],
    )


@router.post("/detect-language", response_model=DetectLanguageResponse)
async def detect_language(payload: DetectLanguageRequest, db: Session = Depends(get_db)) -> DetectLanguageResponse:
    service = TranslationService(db)
    try:
        language, confidence = await service.detect_language(payload.text)
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)

    meta = get_language_by_code(language)
    return DetectLanguageResponse(
        language=language,
        language_name=meta["name"] if meta else None,
        confidence=confidence,
    )


@router.post("/speech/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    db: Session = Depends(get_db),
) -> TranscribeResponse:
    service = TranslationService(db)
    try:
        audio_bytes = await file.read()
        content_type = file.content_type or "audio/wav"
        result = await service.transcribe_speech(
            audio_bytes=audio_bytes,
            content_type=content_type,
            language=language,
        )
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)
    finally:
        await file.close()

    return TranscribeResponse(
        text=result.text,
        language=result.language,
        confidence=result.confidence,
    )


@router.post("/speech/synthesize")
async def synthesize_speech(
    payload: SynthesizeRequest,
    db: Session = Depends(get_db),
) -> Response:
    service = TranslationService(db)
    try:
        result = await service.synthesize_speech(
            text=payload.text,
            language=payload.language,
            speed=payload.speed,
            voice=payload.voice,
        )
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)

    return Response(
        content=result.audio_bytes,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'inline; filename="speech.{result.format}"',
            "Cache-Control": "no-cache",
        },
    )


# ============================================================================
# Stage 4: Real-Time Streaming Voice Translation
# ============================================================================


@router.websocket("/voice/stream")
async def websocket_voice_stream(
    websocket: WebSocket,
    source_language: str = Query(default="en"),
    target_language: str = Query(default="ta"),
    translation_style: str = Query(default="general"),
    db: Session = Depends(get_db),
) -> None:
    service = VoiceTranslationService(db)
    await service.handle_websocket_stream(
        websocket=websocket,
        source_language=source_language,
        target_language=target_language,
        translation_style=translation_style,
    )


@router.post("/voice/translate-speech", response_model=TranslateResponse)
async def translate_voice_speech(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    source_language: str = Form("auto"),
    translation_style: str = Form("general"),
    db: Session = Depends(get_db),
) -> TranslateResponse:
    service = TranslationService(db)
    try:
        audio_bytes = await file.read()
        content_type = file.content_type or "audio/webm"
        transcription = await service.transcribe_speech(
            audio_bytes=audio_bytes,
            content_type=content_type,
            language=source_language if source_language != "auto" else None,
        )
        if not transcription.text.strip():
            raise AppError("No speech could be recognized from the audio recording.")
        source, target, translated, style, method, detected, history_id = await service.translate(
            text=transcription.text,
            source_language=source_language,
            target_language=target_language,
            style=translation_style,
            input_method="voice",
        )
        return TranslateResponse(
            source_language=source,
            target_language=target,
            original_text=transcription.text,
            translated_text=translated,
            translation_style=style,
            input_method="voice",
            detected_language=detected or transcription.language,
            history_id=history_id,
        )
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)
    finally:
        await file.close()



@router.get("/history", response_model=HistoryListResponse)
def get_history(
    input_method: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> HistoryListResponse:
    service = TranslationService(db)
    items, total = service.list_history(input_method=input_method, search=search, limit=limit, offset=offset)
    return HistoryListResponse(
        items=[HistoryItem.model_validate(item) for item in items],
        total=total,
    )


@router.delete("/history/{history_id}", status_code=204)
def delete_history(history_id: int, db: Session = Depends(get_db)) -> None:
    service = TranslationService(db)
    try:
        service.delete_history(history_id)
    except AppError as exc:
        raise_http_error(exc)


# ============================================================================
# Stage 3: OCR & Image Translation
# ============================================================================


@router.post("/ocr/extract", response_model=OCRExtractResponse)
async def extract_ocr(
    file: UploadFile = File(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
) -> OCRExtractResponse:
    uploaded = file or image
    if not uploaded:
        raise_http_error(AppError("Image file is required."))
    service = TranslationService(db)
    try:
        content = await uploaded.read()
        res = await service.extract_ocr(
            content,
            filename=uploaded.filename or "image.png",
            content_type=uploaded.content_type or "image/png",
        )
        return OCRExtractResponse(**res)
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)
    finally:
        await uploaded.close()


@router.post("/image/translate", response_model=ImageTranslateResponse)
async def translate_image(
    file: UploadFile = File(None),
    image: UploadFile = File(None),
    target_language: str = Form(...),
    source_language: str = Form("auto"),
    translation_style: str = Form("general"),
    db: Session = Depends(get_db),
) -> ImageTranslateResponse:
    uploaded = file or image
    if not uploaded:
        raise_http_error(AppError("Image file is required."))
    service = TranslationService(db)
    try:
        content = await uploaded.read()
        res = await service.translate_image(
            image_bytes=content,
            target_language=target_language,
            source_language=source_language,
            translation_style=translation_style,
            filename=uploaded.filename or "image.png",
            content_type=uploaded.content_type or "image/png",
        )
        return ImageTranslateResponse(**res)
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)
    finally:
        await uploaded.close()


# ============================================================================
# Stage 3: Document Translation (PDF, DOCX, TXT)
# ============================================================================


@router.post("/documents/translate", response_model=DocumentItem)
async def translate_document(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    source_language: str = Form("auto"),
    translation_style: str = Form("general"),
    db: Session = Depends(get_db),
) -> DocumentItem:
    service = DocumentTranslationService(db)
    try:
        content = await file.read()
        doc = await service.process_document(
            file_bytes=content,
            filename=file.filename or "document.txt",
            content_type=file.content_type or "application/octet-stream",
            target_language=target_language,
            source_language=source_language,
            translation_style=translation_style,
        )
        item = DocumentItem.model_validate(doc)
        item.download_url = f"/api/documents/{doc.id}/download"
        return item
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)
    finally:
        await file.close()


@router.post("/documents/pdf/translate", response_model=DocumentItem)
async def translate_pdf_document(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    source_language: str = Form("auto"),
    translation_style: str = Form("general"),
    db: Session = Depends(get_db),
) -> DocumentItem:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise_http_error(AppError("Only PDF documents (.pdf) are supported at this endpoint."))
    return await translate_document(
        file=file,
        target_language=target_language,
        source_language=source_language,
        translation_style=translation_style,
        db=db,
    )


@router.post("/documents/txt/translate", response_model=DocumentItem)
async def translate_txt_document(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    source_language: str = Form("auto"),
    translation_style: str = Form("general"),
    db: Session = Depends(get_db),
) -> DocumentItem:
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise_http_error(AppError("Only TXT documents (.txt) are supported at this endpoint."))
    return await translate_document(
        file=file,
        target_language=target_language,
        source_language=source_language,
        translation_style=translation_style,
        db=db,
    )


@router.post("/documents/docx/translate", response_model=DocumentItem)
async def translate_docx_document(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    source_language: str = Form("auto"),
    translation_style: str = Form("general"),
    db: Session = Depends(get_db),
) -> DocumentItem:
    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        raise_http_error(AppError("Only DOCX documents (.docx) are supported at this endpoint."))
    return await translate_document(
        file=file,
        target_language=target_language,
        source_language=source_language,
        translation_style=translation_style,
        db=db,
    )



@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    service = DocumentTranslationService(db)
    items, total = service.list_documents(limit=limit, offset=offset)
    result_items = []
    for d in items:
        item = DocumentItem.model_validate(d)
        item.download_url = f"/api/documents/{d.id}/download"
        result_items.append(item)
    return DocumentListResponse(items=result_items, total=total)


@router.get("/documents/{doc_id}", response_model=DocumentItem)
def get_document(doc_id: int, db: Session = Depends(get_db)) -> DocumentItem:
    service = DocumentTranslationService(db)
    try:
        doc = service.get_document(doc_id)
        item = DocumentItem.model_validate(doc)
        item.download_url = f"/api/documents/{doc.id}/download"
        return item
    except AppError as exc:
        raise_http_error(exc)


@router.get("/documents/{doc_id}/download")
def download_document(doc_id: int, db: Session = Depends(get_db)) -> FileResponse:
    service = DocumentTranslationService(db)
    try:
        doc = service.get_document(doc_id)
        if not doc.output_path or not os.path.exists(doc.output_path):
            raise AppError("Document file is missing or has expired.", status_code=404)

        # Path traversal protection
        storage_root = service.settings.storage_path.resolve()
        resolved_path = Path(doc.output_path).resolve()
        try:
            is_safe = resolved_path.is_relative_to(storage_root)
        except AttributeError:
            is_safe = str(resolved_path).startswith(str(storage_root))

        if not is_safe:
            raise AppError("Access denied.", status_code=403)

        media_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain; charset=utf-8",
        }
        media_type = media_types.get(doc.document_type, "application/octet-stream")
        return FileResponse(
            path=str(resolved_path),
            filename=doc.download_filename,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{doc.download_filename}"'},
        )
    except AppError as exc:
        raise_http_error(exc)


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_db)) -> None:
    service = DocumentTranslationService(db)
    try:
        service.delete_document(doc_id)
    except AppError as exc:
        raise_http_error(exc)


# ============================================================================
# Stage 3: Conversation Mode
# ============================================================================


@router.post("/conversations/sessions", response_model=ConversationSessionItem)
def create_conversation_session(
    payload: CreateSessionRequest,
    db: Session = Depends(get_db),
) -> ConversationSessionItem:
    service = ConversationService(db)
    try:
        session = service.create_session(
            language_a=payload.language_a,
            language_b=payload.language_b,
            title=payload.title,
        )
        return ConversationSessionItem.model_validate(session)
    except AppError as exc:
        raise_http_error(exc)


@router.get("/conversations/sessions", response_model=ConversationSessionListResponse)
def list_conversation_sessions(
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ConversationSessionListResponse:
    service = ConversationService(db)
    sessions, total = service.list_sessions(search=search, limit=limit, offset=offset)
    result_items = []
    for s in sessions:
        item = ConversationSessionItem.model_validate(s)
        item.message_count = len(s.messages)
        result_items.append(item)
    return ConversationSessionListResponse(items=result_items, total=total)


@router.get("/conversations/sessions/{session_id}", response_model=ConversationSessionItem)
def get_conversation_session(session_id: int, db: Session = Depends(get_db)) -> ConversationSessionItem:
    service = ConversationService(db)
    try:
        session = service.get_session(session_id)
        item = ConversationSessionItem.model_validate(session)
        item.message_count = len(session.messages)
        return item
    except AppError as exc:
        raise_http_error(exc)


@router.delete("/conversations/sessions/{session_id}", status_code=204)
def delete_conversation_session(session_id: int, db: Session = Depends(get_db)) -> None:
    service = ConversationService(db)
    try:
        service.delete_session(session_id)
    except AppError as exc:
        raise_http_error(exc)


@router.post("/conversations/sessions/{session_id}/swap", response_model=ConversationSessionItem)
def swap_conversation_session_languages(
    session_id: int, db: Session = Depends(get_db)
) -> ConversationSessionItem:
    service = ConversationService(db)
    try:
        session = service.swap_languages(session_id)
        item = ConversationSessionItem.model_validate(session)
        item.message_count = len(session.messages)
        return item
    except AppError as exc:
        raise_http_error(exc)


@router.patch("/conversations/sessions/{session_id}", response_model=ConversationSessionItem)
def update_conversation_session(
    session_id: int,
    payload: UpdateSessionRequest,
    db: Session = Depends(get_db),
) -> ConversationSessionItem:
    service = ConversationService(db)
    try:
        session = service.update_session(
            session_id=session_id,
            language_a=payload.language_a,
            language_b=payload.language_b,
            title=payload.title,
        )
        item = ConversationSessionItem.model_validate(session)
        item.message_count = len(session.messages)
        return item
    except AppError as exc:
        raise_http_error(exc)


# Aliases for /conversations
@router.post("/conversations", response_model=ConversationSessionItem)
def create_conversation_alias(payload: CreateSessionRequest, db: Session = Depends(get_db)) -> ConversationSessionItem:
    return create_conversation_session(payload=payload, db=db)


@router.get("/conversations", response_model=ConversationSessionListResponse)
def list_conversations_alias(
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ConversationSessionListResponse:
    return list_conversation_sessions(search=search, limit=limit, offset=offset, db=db)


@router.get("/conversations/{session_id}", response_model=ConversationSessionItem)
def get_conversation_alias(session_id: int, db: Session = Depends(get_db)) -> ConversationSessionItem:
    return get_conversation_session(session_id=session_id, db=db)


@router.delete("/conversations/{session_id}", status_code=204)
def delete_conversation_alias(session_id: int, db: Session = Depends(get_db)) -> None:
    delete_conversation_session(session_id=session_id, db=db)


@router.post("/conversations/{session_id}/swap", response_model=ConversationSessionItem)
def swap_conversation_alias(session_id: int, db: Session = Depends(get_db)) -> ConversationSessionItem:
    return swap_conversation_session_languages(session_id=session_id, db=db)


@router.post("/conversations/{session_id}/messages", response_model=ConversationMessageItem)
async def send_conversation_message_alias(
    session_id: int, payload: SendMessageRequest, db: Session = Depends(get_db)
) -> ConversationMessageItem:
    return await send_conversation_message(session_id=session_id, payload=payload, db=db)


@router.post("/conversations/{session_id}/messages/audio", response_model=ConversationMessageItem)
async def send_conversation_audio_message_alias(
    session_id: int, file: UploadFile = File(...), speaker: str = Form(...), db: Session = Depends(get_db)
) -> ConversationMessageItem:
    return await send_conversation_audio_message(session_id=session_id, file=file, speaker=speaker, db=db)


@router.post("/conversations/sessions/{session_id}/messages", response_model=ConversationMessageItem)
async def send_conversation_message(
    session_id: int,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
) -> ConversationMessageItem:
    service = ConversationService(db)
    try:
        msg = await service.send_message(
            session_id=session_id,
            speaker=payload.speaker,
            text=payload.text,
        )
        return ConversationMessageItem.model_validate(msg)
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)


@router.post("/conversations/sessions/{session_id}/messages/audio", response_model=ConversationMessageItem)
async def send_conversation_audio_message(
    session_id: int,
    file: UploadFile = File(...),
    speaker: str = Form(...),
    db: Session = Depends(get_db),
) -> ConversationMessageItem:
    service = ConversationService(db)
    try:
        content = await file.read()
        content_type = file.content_type or "audio/wav"
        msg = await service.send_audio_message(
            session_id=session_id,
            speaker=speaker,
            audio_bytes=content,
            content_type=content_type,
        )
        return ConversationMessageItem.model_validate(msg)
    except AppError as exc:
        raise_http_error(exc)
    except ProviderError as exc:
        raise_http_error(exc)
    finally:
        await file.close()


# ============================================================================
# Stage 3: Multimodal History
# ============================================================================


@router.get("/history/multimodal", response_model=MultimodalHistoryResponse)
def get_multimodal_history(
    modality: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> MultimodalHistoryResponse:
    trans_service = TranslationService(db)
    doc_service = DocumentTranslationService(db)
    conv_service = ConversationService(db)

    results: list[MultimodalHistoryItem] = []

    # 1. Translations (text, voice, image)
    fetch_translations = modality is None or modality.lower() in ("all", "text", "voice", "image")
    if fetch_translations:
        filter_method = None if (modality is None or modality.lower() == "all") else modality.lower()
        items, _ = trans_service.list_history(
            input_method=filter_method, search=search, limit=limit, offset=offset
        )
        for t in items:
            mod = t.input_method if t.input_method in ("text", "voice", "image") else "text"
            title = f"{t.source_language.upper()} ➔ {t.target_language.upper()}"
            results.append(
                MultimodalHistoryItem(
                    id=f"trans-{t.id}",
                    raw_id=t.id,
                    modality=mod,
                    title=title,
                    source_language=t.source_language,
                    target_language=t.target_language,
                    original_text=t.original_text,
                    translated_text=t.translated_text,
                    created_at=t.created_at,
                )
            )

    # 2. Documents
    fetch_docs = modality is None or modality.lower() in ("all", "document")
    if fetch_docs:
        docs, _ = doc_service.list_documents(limit=limit, offset=offset)
        for d in docs:
            if search and search.strip():
                s = search.strip().lower()
                if (
                    s not in d.filename.lower()
                    and s not in d.original_text_sample.lower()
                    and s not in d.translated_text_sample.lower()
                ):
                    continue
            results.append(
                MultimodalHistoryItem(
                    id=f"doc-{d.id}",
                    raw_id=d.id,
                    modality="document",
                    title=f"Document: {d.filename}",
                    source_language=d.source_language,
                    target_language=d.target_language,
                    original_text=d.original_text_sample,
                    translated_text=d.translated_text_sample,
                    created_at=d.created_at,
                    document_type=d.document_type,
                    download_url=f"/api/documents/{d.id}/download",
                )
            )

    # 3. Conversations
    fetch_convs = modality is None or modality.lower() in ("all", "conversation")
    if fetch_convs:
        sessions, _ = conv_service.list_sessions(search=search, limit=limit, offset=offset)
        for s in sessions:
            orig = f"{len(s.messages)} message(s) in session."
            trans = s.title
            if s.messages:
                last_msg = s.messages[-1]
                orig = f"Last message: {last_msg.original_text}"
                trans = f"Translation: {last_msg.translated_text}"
            results.append(
                MultimodalHistoryItem(
                    id=f"conv-{s.id}",
                    raw_id=s.id,
                    modality="conversation",
                    title=s.title,
                    source_language=s.language_a,
                    target_language=s.language_b,
                    original_text=orig,
                    translated_text=trans,
                    created_at=s.updated_at or s.created_at,
                    session_id=s.id,
                )
            )

    # Sort all results by created_at descending
    results.sort(key=lambda x: x.created_at, reverse=True)
    total = len(results)
    paged = results[offset : offset + limit]
    return MultimodalHistoryResponse(items=paged, total=total)


