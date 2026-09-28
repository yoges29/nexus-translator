import inspect
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.errors import AppError, ProviderError
from app.services.translation_service import TranslationService

logger = logging.getLogger("nexus.translator.voice")


class VoiceTranslationService:
    """Manages real-time streaming voice transcription and translation over WebSockets."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.translation_service = TranslationService(db)

    async def handle_websocket_stream(
        self,
        websocket: WebSocket,
        source_language: str = "en",
        target_language: str = "ta",
        translation_style: str = "general",
    ) -> None:
        await websocket.accept()
        logger.info(
            "WebSocket voice stream connected: source=%s, target=%s, style=%s",
            source_language,
            target_language,
            translation_style,
        )

        # Send initial confirmation
        await websocket.send_json(
            {
                "type": "ready",
                "source_language": source_language,
                "target_language": target_language,
                "translation_style": translation_style,
                "message": "Voice streaming channel connected and ready.",
            }
        )

        current_source = source_language
        current_target = target_language
        current_style = translation_style

        accumulated_audio = bytearray()
        last_recognized_text = ""
        is_transcribing = False

        try:
            while True:
                # Receive message frame (text JSON or binary audio)
                message = await websocket.receive()

                if "text" in message and message["text"]:
                    try:
                        payload: dict[str, Any] = json.loads(message["text"])
                    except json.JSONDecodeError:
                        await websocket.send_json({"type": "error", "message": "Invalid JSON frame."})
                        continue

                    msg_type = payload.get("type", "transcript")

                    # Configuration update frame
                    if msg_type == "config":
                        current_source = payload.get("source_language", current_source)
                        current_target = payload.get("target_language", current_target)
                        current_style = payload.get("translation_style", current_style)
                        accumulated_audio.clear()
                        last_recognized_text = ""
                        await websocket.send_json(
                            {
                                "type": "config_updated",
                                "source_language": current_source,
                                "target_language": current_target,
                                "translation_style": current_style,
                            }
                        )
                        continue

                    # Reset audio stream buffer frame
                    if msg_type in ("reset_audio", "clear"):
                        accumulated_audio.clear()
                        last_recognized_text = ""
                        continue

                    # Ping frame for keepalive
                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                        continue

                    # Transcript frame (from client Web Speech API or streaming STT)
                    if msg_type == "transcript":
                        text = payload.get("text", "").strip()
                        is_final = bool(payload.get("is_final", False))

                        if not text:
                            continue

                        # If partial/interim transcript: quickly translate or echo
                        if not is_final:
                            # Fast interim translation
                            try:
                                translated_interim = await self._quick_translate(
                                    text, current_source, current_target, current_style
                                )
                                await websocket.send_json(
                                    {
                                        "type": "interim",
                                        "original_text": text,
                                        "translated_text": translated_interim,
                                        "source_language": current_source,
                                        "target_language": current_target,
                                    }
                                )
                            except Exception as exc:
                                logger.debug("Interim translation skipped: %s", exc)
                                await websocket.send_json(
                                    {
                                        "type": "interim",
                                        "original_text": text,
                                        "translated_text": "",
                                        "source_language": current_source,
                                        "target_language": current_target,
                                    }
                                )
                            continue

                        # Finalized transcript: full translation and DB persistence
                        try:
                            (
                                resolved_src,
                                resolved_tgt,
                                translated_text,
                                style_used,
                                method,
                                detected_lang,
                                history_id,
                            ) = await self.translation_service.translate(
                                text=text,
                                source_language=current_source,
                                target_language=current_target,
                                style=current_style,
                                input_method="voice",
                            )

                            await websocket.send_json(
                                {
                                    "type": "final",
                                    "original_text": text,
                                    "translated_text": translated_text,
                                    "source_language": resolved_src,
                                    "target_language": resolved_tgt,
                                    "detected_language": detected_lang,
                                    "translation_style": style_used,
                                    "history_id": history_id,
                                }
                            )
                        except (AppError, ProviderError) as exc:
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": exc.message,
                                    "status_code": getattr(exc, "status_code", 400),
                                }
                            )
                        except Exception as exc:
                            logger.exception("Final voice translation error: %s", exc)
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": "Failed to translate recognized speech.",
                                }
                            )

                elif "bytes" in message and message["bytes"]:
                    # Binary audio chunk frame from client MediaRecorder or AudioContext
                    audio_bytes: bytes = message["bytes"]
                    if len(audio_bytes) < 32:
                        continue

                    # Check audio container format
                    is_wav = audio_bytes.startswith(b"RIFF") and b"WAVE" in audio_bytes[:16]
                    if is_wav:
                        audio_to_transcribe = audio_bytes
                        c_type = "audio/wav"
                    else:
                        c_type = "audio/webm"
                        if audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
                            accumulated_audio = bytearray(audio_bytes)
                        else:
                            accumulated_audio.extend(audio_bytes)
                        audio_to_transcribe = bytes(accumulated_audio)

                    logger.debug(
                        "Received audio chunk: size=%d bytes, format=%s, total_buffered=%d bytes",
                        len(audio_bytes),
                        c_type,
                        len(audio_to_transcribe),
                    )

                    # Only transcribe when sufficient audio has buffered (>= 6000 bytes) and not already transcribing
                    if len(audio_to_transcribe) >= 6000 and not is_transcribing:
                        is_transcribing = True

                        async def _process_chunk(
                            chunk_data: bytes,
                            content_type: str,
                            src_lang: str,
                            tgt_lang: str,
                            style: str,
                        ) -> None:
                            nonlocal is_transcribing, last_recognized_text
                            try:
                                transcription = await self.translation_service.transcribe_speech(
                                    audio_bytes=chunk_data,
                                    content_type=content_type,
                                    language=src_lang if src_lang != "auto" else None,
                                )

                                text = transcription.text.strip()
                                if text and text.lower() != last_recognized_text.lower():
                                    last_recognized_text = text
                                    logger.info("Real-time voice recognized text: length=%d", len(text))

                                    (
                                        resolved_src,
                                        resolved_tgt,
                                        translated_text,
                                        style_used,
                                        method,
                                        detected_lang,
                                        history_id,
                                    ) = await self.translation_service.translate(
                                        text=text,
                                        source_language=src_lang,
                                        target_language=tgt_lang,
                                        style=style,
                                        input_method="voice",
                                    )

                                    await websocket.send_json(
                                        {
                                            "type": "final",
                                            "original_text": text,
                                            "translated_text": translated_text,
                                            "source_language": resolved_src,
                                            "target_language": resolved_tgt,
                                            "detected_language": detected_lang,
                                            "confidence": transcription.confidence,
                                            "translation_style": style_used,
                                            "history_id": history_id,
                                        }
                                    )
                                    # Clear buffer after successful transcription of phrase
                                    accumulated_audio.clear()
                            except AppError as exc:
                                # Normal silence or non-speech interval during streaming
                                logger.debug("Stream audio chunk not recognized yet: %s", exc)
                            except Exception as exc:
                                logger.warning("Stream audio chunk transcription error: %s", exc)
                            finally:
                                is_transcribing = False

                        import asyncio
                        asyncio.create_task(
                            _process_chunk(
                                audio_to_transcribe,
                                c_type,
                                current_source,
                                current_target,
                                current_style,
                            )
                        )

        except WebSocketDisconnect:
            logger.info("WebSocket voice stream disconnected cleanly by client.")
        except RuntimeError as exc:
            if "disconnect" in str(exc).lower() or "cannot call" in str(exc).lower():
                logger.info("WebSocket voice stream disconnected cleanly by client.")
            else:
                logger.exception("Runtime error in voice WebSocket stream: %s", exc)
        except Exception as exc:
            logger.exception("Unexpected error in voice WebSocket stream: %s", exc)
            try:
                await websocket.send_json({"type": "error", "message": "WebSocket connection encountered an error."})
            except Exception:
                pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    async def _quick_translate(
        self, text: str, source: str, target: str, style: str
    ) -> str:
        src = source
        if src == "auto":
            from app.services.detector import LanguageDetector
            det = LanguageDetector.detect(text)
            src = det.language if (det and det.language != target) else "en"
        provider = self.translation_service.provider
        res = provider.translate(text, src, target, style=style)
        if inspect.isawaitable(res):
            res = await res
        return str(res)

