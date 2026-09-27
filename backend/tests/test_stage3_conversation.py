import io


def test_conversation_create_and_get(client, mock_provider):
    res = client.post(
        "/api/conversations/sessions",
        json={"language_a": "ta", "language_b": "en", "title": "Tamil ⇄ English Test"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language_a"] == "ta"
    assert data["language_b"] == "en"
    assert data["title"] == "Tamil ⇄ English Test"
    session_id = data["id"]

    get_res = client.get(f"/api/conversations/sessions/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == session_id
    assert get_res.json()["messages"] == []


def test_conversation_text_exchange(client, mock_provider):
    res = client.post(
        "/api/conversations/sessions",
        json={"language_a": "ta", "language_b": "en"},
    )
    session_id = res.json()["id"]

    # Speaker A speaks Tamil
    msg_a = client.post(
        f"/api/conversations/sessions/{session_id}/messages",
        json={"speaker": "speaker_a", "text": "நீங்கள் எங்கே செல்கிறீர்கள்?"},
    )
    assert msg_a.status_code == 200
    data_a = msg_a.json()
    assert data_a["speaker"] == "speaker_a"
    assert data_a["source_language"] == "ta"
    assert data_a["target_language"] == "en"
    assert data_a["original_text"] == "நீங்கள் எங்கே செல்கிறீர்கள்?"
    assert "translated_text" in data_a

    # Speaker B replies in English
    msg_b = client.post(
        f"/api/conversations/sessions/{session_id}/messages",
        json={"speaker": "speaker_b", "text": "I am going to the station."},
    )
    assert msg_b.status_code == 200
    data_b = msg_b.json()
    assert data_b["speaker"] == "speaker_b"
    assert data_b["source_language"] == "en"
    assert data_b["target_language"] == "ta"
    assert data_b["original_text"] == "I am going to the station."
    assert "translated_text" in data_b

    # Verify session messages list
    get_res = client.get(f"/api/conversations/sessions/{session_id}")
    assert get_res.status_code == 200
    messages = get_res.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["speaker"] == "speaker_a"
    assert messages[1]["speaker"] == "speaker_b"


def test_conversation_audio_exchange(client, mock_provider, mock_stt):
    res = client.post(
        "/api/conversations/sessions",
        json={"language_a": "en", "language_b": "es"},
    )
    session_id = res.json()["id"]

    fake_audio = io.BytesIO(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    audio_res = client.post(
        f"/api/conversations/sessions/{session_id}/messages/audio",
        files={"file": ("voice.wav", fake_audio, "audio/wav")},
        data={"speaker": "speaker_a"},
    )
    assert audio_res.status_code == 200
    data = audio_res.json()
    assert data["speaker"] == "speaker_a"
    assert data["source_language"] == "en"
    assert data["target_language"] == "es"
    assert data["original_text"] == "Hello world speech"


def test_conversation_swap_languages(client, mock_provider):
    res = client.post(
        "/api/conversations/sessions",
        json={"language_a": "ta", "language_b": "en"},
    )
    session_id = res.json()["id"]

    # First message under original orientation (A is ta, B is en)
    msg1 = client.post(
        f"/api/conversations/sessions/{session_id}/messages",
        json={"speaker": "speaker_a", "text": "முதல் செய்தி"},
    )
    assert msg1.status_code == 200
    assert msg1.json()["source_language"] == "ta"

    # Swap languages (A becomes en, B becomes ta)
    swap_res = client.post(f"/api/conversations/sessions/{session_id}/swap")
    assert swap_res.status_code == 200
    swap_data = swap_res.json()
    assert swap_data["language_a"] == "en"
    assert swap_data["language_b"] == "ta"

    # New message from speaker A now uses en as source
    msg2 = client.post(
        f"/api/conversations/sessions/{session_id}/messages",
        json={"speaker": "speaker_a", "text": "Now speaking in English"},
    )
    assert msg2.status_code == 200
    assert msg2.json()["source_language"] == "en"
    assert msg2.json()["target_language"] == "ta"

    # Check that previous message retained its original language
    get_res = client.get(f"/api/conversations/sessions/{session_id}")
    msgs = get_res.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["source_language"] == "ta"
    assert msgs[1]["source_language"] == "en"


def test_conversation_update_session(client, mock_provider):
    res = client.post(
        "/api/conversations/sessions",
        json={"language_a": "en", "language_b": "fr"},
    )
    session_id = res.json()["id"]

    patch_res = client.patch(
        f"/api/conversations/sessions/{session_id}",
        json={"language_b": "de", "title": "English ⇄ German Updated"},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["language_a"] == "en"
    assert data["language_b"] == "de"
    assert data["title"] == "English ⇄ German Updated"


def test_conversation_aliases(client, mock_provider):
    # Test /api/conversations alias
    create_res = client.post(
        "/api/conversations",
        json={"language_a": "es", "language_b": "en"},
    )
    assert create_res.status_code == 200
    session_id = create_res.json()["id"]

    # Test list alias
    list_res = client.get("/api/conversations")
    assert list_res.status_code == 200
    assert any(s["id"] == session_id for s in list_res.json()["items"])

    # Test get alias
    get_res = client.get(f"/api/conversations/{session_id}")
    assert get_res.status_code == 200

    # Test swap alias
    swap_res = client.post(f"/api/conversations/{session_id}/swap")
    assert swap_res.status_code == 200
    assert swap_res.json()["language_a"] == "en"
    assert swap_res.json()["language_b"] == "es"

    # Test message alias
    msg_res = client.post(
        f"/api/conversations/{session_id}/messages",
        json={"speaker": "speaker_a", "text": "Hello alias test"},
    )
    assert msg_res.status_code == 200

    # Test delete alias
    del_res = client.delete(f"/api/conversations/{session_id}")
    assert del_res.status_code == 204
    assert client.get(f"/api/conversations/{session_id}").status_code == 404


def test_conversation_validation_errors(client, mock_provider):
    # 1. Unsupported language
    res1 = client.post(
        "/api/conversations/sessions",
        json={"language_a": "klingon", "language_b": "en"},
    )
    assert res1.status_code == 400
    assert "Unsupported language" in res1.json()["detail"]

    # 2. Same language
    res2 = client.post(
        "/api/conversations/sessions",
        json={"language_a": "en", "language_b": "en"},
    )
    assert res2.status_code == 400
    assert "different" in res2.json()["detail"].lower()

    # 3. Create valid session
    valid = client.post(
        "/api/conversations/sessions",
        json={"language_a": "en", "language_b": "fr"},
    )
    session_id = valid.json()["id"]

    # 4. Empty message text
    res3 = client.post(
        f"/api/conversations/sessions/{session_id}/messages",
        json={"speaker": "speaker_a", "text": "   "},
    )
    assert res3.status_code in (400, 422)

    # 5. Invalid speaker
    res4 = client.post(
        f"/api/conversations/sessions/{session_id}/messages",
        json={"speaker": "speaker_xyz", "text": "Hello"},
    )
    assert res4.status_code in (400, 422)

    # 6. Non-existent session
    res5 = client.get("/api/conversations/sessions/999999")
    assert res5.status_code == 404


def test_conversation_multimodal_history_and_delete(client, mock_provider):
    create_res = client.post(
        "/api/conversations/sessions",
        json={"language_a": "ta", "language_b": "en", "title": "History Check"},
    )
    session_id = create_res.json()["id"]

    client.post(
        f"/api/conversations/sessions/{session_id}/messages",
        json={"speaker": "speaker_a", "text": "சென்னையில் மழை பெய்கிறது"},
    )

    # Check multimodal history
    multi_res = client.get("/api/history/multimodal?modality=conversation")
    assert multi_res.status_code == 200
    items = multi_res.json()["items"]
    assert any(m["raw_id"] == session_id and m["modality"] == "conversation" for m in items)

    # Delete session
    del_res = client.delete(f"/api/conversations/sessions/{session_id}")
    assert del_res.status_code == 204

    # Verify 404
    assert client.get(f"/api/conversations/sessions/{session_id}").status_code == 404
