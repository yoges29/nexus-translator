import inspect
import logging
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, ProviderError
from app.core.languages import get_language_by_code, is_translation_supported
from app.models.conversation import ConversationMessage, ConversationSession
from app.services.provider_factory import get_stt_provider, get_translation_provider

logger = logging.getLogger("nexus.translator.conversation")


class ConversationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.translation_provider = get_translation_provider()
        self.stt_provider = get_stt_provider()

    def create_session(
        self,
        language_a: str,
        language_b: str,
        title: str | None = None,
        user_id: int | None = None,
    ) -> ConversationSession:
        lang_a = language_a.strip().lower()
        lang_b = language_b.strip().lower()

        if not is_translation_supported(lang_a):
            raise AppError(f"Unsupported language A: {lang_a}")
        if not is_translation_supported(lang_b):
            raise AppError(f"Unsupported language B: {lang_b}")
        if lang_a == lang_b:
            raise AppError("Speaker languages must be different.")

        if not title:
            meta_a = get_language_by_code(lang_a)
            meta_b = get_language_by_code(lang_b)
            name_a = meta_a["name"] if meta_a else lang_a.upper()
            name_b = meta_b["name"] if meta_b else lang_b.upper()
            title = f"{name_a} ⇄ {name_b} Conversation"

        session = ConversationSession(
            user_id=user_id,
            title=title,
            language_a=lang_a,
            language_b=lang_b,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: int) -> ConversationSession:
        session = (
            self.db.query(ConversationSession)
            .options(joinedload(ConversationSession.messages))
            .filter(ConversationSession.id == session_id)
            .first()
        )
        if not session:
            raise AppError("Conversation session not found.", status_code=404)
        return session

    def list_sessions(
        self,
        user_id: int | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ConversationSession], int]:
        query = self.db.query(ConversationSession)
        if user_id is not None:
            query = query.filter(ConversationSession.user_id == user_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    ConversationSession.title.ilike(term),
                    ConversationSession.language_a.ilike(term),
                    ConversationSession.language_b.ilike(term),
                )
            )

        total = query.count()
        sessions = (
            query.order_by(ConversationSession.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return sessions, total

    def update_session(
        self,
        session_id: int,
        language_a: str | None = None,
        language_b: str | None = None,
        title: str | None = None,
    ) -> ConversationSession:
        session = self.get_session(session_id)
        if language_a is not None:
            lang_a = language_a.strip().lower()
            if not is_translation_supported(lang_a):
                raise AppError(f"Unsupported language A: {lang_a}")
            session.language_a = lang_a
        if language_b is not None:
            lang_b = language_b.strip().lower()
            if not is_translation_supported(lang_b):
                raise AppError(f"Unsupported language B: {lang_b}")
            session.language_b = lang_b
        if session.language_a == session.language_b:
            raise AppError("Speaker languages must be different.")
        if title is not None and title.strip():
            session.title = title.strip()
        session.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return session

    def swap_languages(self, session_id: int) -> ConversationSession:
        session = self.get_session(session_id)
        session.language_a, session.language_b = session.language_b, session.language_a
        session.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: int) -> None:
        session = self.db.get(ConversationSession, session_id)
        if not session:
            raise AppError("Conversation session not found.", status_code=404)
        self.db.delete(session)
        self.db.commit()

    async def send_message(
        self,
        session_id: int,
        speaker: str,
        text: str,
    ) -> ConversationMessage:
        session = self.get_session(session_id)
        cleaned = text.strip()
        if not cleaned:
            raise AppError("Message text cannot be empty.")

        speaker_norm = speaker.strip().lower()
        if speaker_norm not in ("speaker_a", "speaker_b"):
            raise AppError("Invalid speaker. Expected 'speaker_a' or 'speaker_b'.")

        if speaker_norm == "speaker_a":
            source_lang = session.language_a
            target_lang = session.language_b
        else:
            source_lang = session.language_b
            target_lang = session.language_a

        try:
            res = self.translation_provider.translate(
                cleaned, source_lang, target_lang, style="general"
            )
            if inspect.isawaitable(res):
                res = await res
            translated = res
        except ProviderError:
            raise
        except Exception as exc:
            logger.exception("Translation error during conversation: %s", exc)
            raise ProviderError("Failed to translate message.") from exc

        msg = ConversationMessage(
            session_id=session.id,
            speaker=speaker_norm,
            source_language=source_lang,
            target_language=target_lang,
            original_text=cleaned,
            translated_text=translated,
        )
        self.db.add(msg)
        session.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    async def send_audio_message(
        self,
        session_id: int,
        speaker: str,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
    ) -> ConversationMessage:
        session = self.get_session(session_id)
        speaker_norm = speaker.strip().lower()
        if speaker_norm not in ("speaker_a", "speaker_b"):
            raise AppError("Invalid speaker. Expected 'speaker_a' or 'speaker_b'.")

        hint_lang = session.language_a if speaker_norm == "speaker_a" else session.language_b

        res = self.stt_provider.transcribe(
            audio_bytes=audio_bytes,
            content_type=content_type,
            language=hint_lang,
        )
        if inspect.isawaitable(res):
            res = await res
        transcription = res

        if not transcription.text.strip():
            raise AppError("No speech could be recognized from the audio.")

        return await self.send_message(
            session_id=session_id,
            speaker=speaker_norm,
            text=transcription.text,
        )
