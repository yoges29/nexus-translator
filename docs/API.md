# NEXUS Translator API — Stage 2

Base URL (local): `http://localhost:8000`

Interactive OpenAPI / Swagger docs: `http://localhost:8000/docs`
ReDoc: `http://localhost:8000/redoc`

---

## 1. Translation Endpoints

### POST `/api/translate`

Translate text between supported languages with stylistic modes and persistent history tracking.

**Request Body** (`application/json`):

```json
{
  "source_language": "en",
  "target_language": "ta",
  "text": "How are you?",
  "translation_style": "general",
  "input_method": "text"
}
```

- `source_language` *(string, required)*: Language code (e.g., `"en"`, `"ta"`, `"hi"`) or `"auto"` for automatic detection.
- `target_language` *(string, required)*: Target language code.
- `text` *(string, required)*: Text to translate (max 20000 characters).
- `translation_style` *(string, optional, default: `"general"`)*: `"general"` | `"formal"` | `"casual"`.
- `input_method` *(string, optional, default: `"text"`)*: `"text"` | `"voice"`.

**Response Body** (`200 OK`):

```json
{
  "source_language": "en",
  "target_language": "ta",
  "original_text": "How are you?",
  "translated_text": "எப்படி இருக்கிறீர்கள்?",
  "translation_style": "general",
  "input_method": "text",
  "detected_language": null,
  "history_id": 42
}
```

---

### POST `/api/translate/alternatives`

Retrieve contextual and stylistic alternative translations (up to 3) preserving original meaning.

**Request Body** (`application/json`):

```json
{
  "source_language": "en",
  "target_language": "ta",
  "text": "How are you?",
  "translation_style": "general"
}
```

**Response Body** (`200 OK`):

```json
{
  "primary": "எப்படி இருக்கிறீர்கள்?",
  "alternatives": [
    "எப்படி இருக்கீங்க?",
    "நலமாக இருக்கிறீர்களா?"
  ]
}
```

---

## 2. Automatic Language Detection

### POST `/api/detect-language`

Detect source language using multi-tier Unicode script analysis, `langdetect`, and provider fallbacks.

**Request Body** (`application/json`):

```json
{
  "text": "வணக்கம், எப்படி இருக்கிறீர்கள்?"
}
```

**Response Body** (`200 OK`):

```json
{
  "language": "ta",
  "language_name": "Tamil",
  "confidence": 0.99
}
```

*Note: Confidence score is only included when provided or calculated by the detector engine; it is never fabricated.*

---

## 3. Speech Processing Endpoints

### POST `/api/speech/transcribe`

Transcribe spoken audio to text with speech recognition providers.

**Request** (`multipart/form-data`):

- `file` *(file, required)*: Audio file upload (`.wav`, `.webm`, `.ogg`, `.mp3`, `.m4a`). Maximum size: 10MB.
- `language` *(string, optional)*: Language code hint (e.g. `"ta"`, `"hi"`, `"en"`).

**Response Body** (`200 OK`):

```json
{
  "text": "Hello, how are you today?",
  "language": "en",
  "confidence": 0.98
}
```

---

### POST `/api/speech/synthesize`

Synthesize text into natural spoken audio via Text-to-Speech (TTS).

**Request Body** (`application/json`):

```json
{
  "text": "வணக்கம், நலமாக இருக்கிறீர்களா?",
  "language": "ta",
  "speed": 1.0,
  "voice": null
}
```

- `text` *(string, required)*: Text to speak.
- `language` *(string, required)*: ISO language code.
- `speed` *(float, optional, default: 1.0)*: Speech playback rate (`0.75`, `1.0`, `1.25`, `1.5`).
- `voice` *(string, optional)*: Preferred voice identifier.

**Response** (`200 OK`):
- `Content-Type`: `audio/mpeg`
- `Content-Disposition`: `inline; filename="speech.mp3"`
- Binary audio stream.

---

## 4. Language Registry & History

### GET `/api/languages`

List all supported languages and their capabilities.

**Response Body** (`200 OK`):

```json
[
  {
    "code": "auto",
    "name": "Auto Detect",
    "nativeName": "Auto Detect",
    "direction": "ltr",
    "translationSupported": false
  },
  {
    "code": "ta",
    "name": "Tamil",
    "nativeName": "தமிழ்",
    "direction": "ltr",
    "translationSupported": true
  }
]
```

---

### GET `/api/history`

Retrieve translation history records (ordered by newest first).

**Response Body** (`200 OK`):

```json
{
  "items": [
    {
      "id": 1,
      "user_id": null,
      "source_language": "en",
      "target_language": "ta",
      "original_text": "How are you?",
      "translated_text": "எப்படி இருக்கிறீர்கள்?",
      "detected_language": "en",
      "translation_style": "general",
      "input_method": "voice",
      "created_at": "2026-09-24T04:20:00Z"
    }
  ],
  "total": 1
}
```

---

### DELETE `/api/history/{id}`

Delete a specific history record by ID.

**Response**: `204 No Content`

---

## 5. Stage 3: OCR & Image Translation

### POST `/api/ocr/extract`

Extract text and bounding box regions from an uploaded image (PNG, JPG, JPEG, WEBP).

**Request Body** (`multipart/form-data`):
- `image` *(file, required)*: Uploaded image file (max 10MB).
- Form field alternative `file` is also supported.

**Response Body** (`200 OK`):

```json
{
  "text": "Hello World",
  "language": "en",
  "regions": [
    {
      "text": "Hello",
      "bounding_box": {
        "x": 10,
        "y": 10,
        "width": 50,
        "height": 20
      },
      "confidence": 0.99
    }
  ]
}
```

---

### POST `/api/image/translate`

Extract text from an image via OCR, automatically detect the source language (if set to `"auto"`), and translate into the target language. Persists an entry in translation history with `input_method="image"`.

**Request Body** (`multipart/form-data`):
- `image` *(file, required)*: Uploaded image file (max 10MB).
- `target_language` *(string, required)*: Target language code (e.g. `"ta"`, `"es"`).
- `source_language` *(string, optional, default: `"auto"`)*: Source language or `"auto"` for automatic detection.
- `translation_style` *(string, optional, default: `"general"`)*: `"general"` | `"formal"` | `"casual"`.

**Response Body** (`200 OK`):

```json
{
  "source_language": "en",
  "target_language": "ta",
  "extracted_text": "Hello world",
  "translated_text": "வணக்கம் உலகம்",
  "detected_language": "en",
  "translation_style": "general",
  "regions": [...],
  "history_id": 42
}
```

---

### Camera Translation Workflow

Camera translation leverages client-side HTML5 `navigator.mediaDevices.getUserMedia` to stream live video, capture a video frame onto an HTML `<canvas>`, serialize it to an `image/jpeg` Blob, and transmit it directly to `POST /api/image/translate`. 

- **Security & Privacy**: Camera streams are explicitly stopped on unmount or tab switch. Frame blobs are held in client memory only and are never saved permanently to disk.
- **Speech Synthesis**: Output translations can be played back on demand using `POST /api/speech/synthesize`.

---

## 6. Stage 3: Document Translation (PDF, DOCX, & TXT)

### POST `/api/documents/translate`
### POST `/api/documents/pdf/translate`
### POST `/api/documents/docx/translate`
### POST `/api/documents/txt/translate`

Upload and translate documents (PDF, DOCX, TXT) up to 20MB.

- **DOCX Workflow**: Extracts text across all sections, headings, paragraphs, bullet lists, tables (cells), and headers/footers. Reconstructs and translates in-place into target language while preserving document structure and styles.
- **PDF Workflow**: Extracts text page-by-page. For scanned documents with minimal text, falls back to OCR on embedded page images. Generates a cleanly formatted translated PDF via ReportLab.
- **TXT Workflow**: Decodes UTF-8 text, translates in chunked paragraphs, and writes translated UTF-8 `.txt` file.

**Request Body** (`multipart/form-data`):
- `file` *(file, required)*: Uploaded document file (.pdf, .docx, .txt).
- `target_language` *(string, required)*: Target language code (e.g. `"en"`, `"ta"`).
- `source_language` *(string, optional, default: `"auto"`)*: Source language or `"auto"` for automatic detection.
- `translation_style` *(string, optional, default: `"general"`)*: `"general"` | `"formal"` | `"casual"`.

**Response Body** (`200 OK`):

```json
{
  "id": 1,
  "filename": "sample.pdf",
  "document_type": "pdf",
  "file_size": 24500,
  "source_language": "ja",
  "target_language": "en",
  "page_count": 2,
  "original_text_sample": "こんにちは...",
  "translated_text_sample": "Hello...",
  "status": "completed",
  "download_filename": "sample_en.pdf",
  "download_url": "/api/documents/1/download",
  "created_at": "2026-09-24T08:00:00Z"
}
```

---

### GET `/api/documents`

List all translated documents.

**Response Body** (`200 OK`):

```json
{
  "items": [...],
  "total": 5
}
```

---

### GET `/api/documents/{id}/download`

Download translated document. Includes path traversal security validation and returns streaming `FileResponse` with `attachment` disposition.

---

### DELETE `/api/documents/{id}`

Permanently delete document database record and generated disk file.

**Response**: `204 No Content`

---

## 7. Stage 3: Two-Party Conversation Mode

### POST `/api/conversations/sessions` (or `POST /api/conversations`)

Create a new bidirectional conversation session between Person A and Person B.

**Request Body** (`application/json`):
```json
{
  "language_a": "ta",
  "language_b": "en",
  "title": "Tamil ⇄ English Conversation"
}
```

**Response Body** (`200 OK`):
```json
{
  "id": 1,
  "user_id": null,
  "title": "Tamil ⇄ English Conversation",
  "language_a": "ta",
  "language_b": "en",
  "created_at": "2026-09-24T09:30:00Z",
  "updated_at": "2026-09-24T09:30:00Z",
  "message_count": 0,
  "messages": []
}
```

---

### POST `/api/conversations/sessions/{id}/messages`

Send a typed message from either speaker (`"speaker_a"` or `"speaker_b"`). The message is translated into the opposite speaker's language and stored in the session.

**Request Body** (`application/json`):
```json
{
  "speaker": "speaker_a",
  "text": "நீங்கள் எங்கே செல்கிறீர்கள்?"
}
```

**Response Body** (`200 OK`):
```json
{
  "id": 10,
  "session_id": 1,
  "speaker": "speaker_a",
  "source_language": "ta",
  "target_language": "en",
  "original_text": "நீங்கள் எங்கே செல்கிறீர்கள்?",
  "translated_text": "Where are you going?",
  "created_at": "2026-09-24T09:31:00Z"
}
```

---

### POST `/api/conversations/sessions/{id}/messages/audio`

Send an audio recording from either speaker. Audio is transcribed via Stage 2 STT, translated, and saved to the session.

**Request Body** (`multipart/form-data`):
- `file` *(file, required)*: Uploaded speech audio file (`audio/wav`, `audio/webm`, `audio/ogg`).
- `speaker` *(string, required)*: `"speaker_a"` | `"speaker_b"`.

**Response Body** (`200 OK`): same schema as `ConversationMessageItem`.

---

### POST `/api/conversations/sessions/{id}/swap`

Swap Person A and Person B languages. Previously recorded messages are strictly preserved; only future messages utilize the swapped orientation.

---

### PATCH `/api/conversations/sessions/{id}`

Update session title or languages.

---

### GET `/api/conversations/sessions` (or `GET /api/conversations`)

List conversation sessions with optional `search`, `limit`, and `offset` query parameters.

---

### GET `/api/conversations/sessions/{id}` (or `GET /api/conversations/{id}`)

Retrieve session details including full chronological messages list.

---

### DELETE `/api/conversations/sessions/{id}` (or `DELETE /api/conversations/{id}`)

Permanently delete conversation session and all associated messages.

**Response**: `204 No Content`

---

## 8. Health Check

### GET `/health`

Check backend API service health.

**Response Body** (`200 OK`):

```json
{
  "status": "ok"
}
```

---

## Error Handling Standards

All errors return standard JSON payloads:

| Status Code | Meaning | Example Payload |
|-------------|---------|-----------------|
| `400 Bad Request` | Validation failure (unsupported language, empty input) | `{"detail": "Text cannot be empty."}` |
| `413 Payload Too Large` | Audio or text exceeds size threshold | `{"detail": "Request payload exceeds size limit."}` |
| `422 Unprocessable Entity` | Schema structure or type error | `{"detail": [...]}` |
| `404 Not Found` | Resource ID not found | `{"detail": "History item not found."}` |
| `503 Service Unavailable` | Provider or network error | `{"detail": "Translation service is temporarily unavailable. Please try again."}` |
