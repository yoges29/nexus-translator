def test_successful_translation(client, mock_provider):
    response = client.post(
        "/api/translate",
        json={"source_language": "en", "target_language": "ta", "text": "Hello"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["translated_text"] == "வணக்கம்"
    assert data["source_language"] == "en"
    assert data["target_language"] == "ta"
    mock_provider.translate.assert_called_once()


def test_empty_input(client, mock_provider):
    response = client.post(
        "/api/translate",
        json={"source_language": "en", "target_language": "ta", "text": "   "},
    )
    assert response.status_code == 422 or response.status_code == 400


def test_too_long_input(client, mock_provider, monkeypatch):
    monkeypatch.setenv("MAX_TEXT_LENGTH", "5")
    from app.core.config import get_settings

    get_settings.cache_clear()
    response = client.post(
        "/api/translate",
        json={"source_language": "en", "target_language": "ta", "text": "123456"},
    )
    assert response.status_code == 400
    get_settings.cache_clear()


def test_invalid_source_language(client, mock_provider):
    response = client.post(
        "/api/translate",
        json={"source_language": "xx", "target_language": "ta", "text": "Hello"},
    )
    assert response.status_code == 400


def test_invalid_target_language(client, mock_provider):
    response = client.post(
        "/api/translate",
        json={"source_language": "en", "target_language": "xx", "text": "Hello"},
    )
    assert response.status_code == 400


def test_same_source_and_target_language(client, mock_provider):
    response = client.post(
        "/api/translate",
        json={"source_language": "en", "target_language": "en", "text": "Hello"},
    )
    assert response.status_code == 400


def test_translation_provider_failure(client, failing_provider):
    response = client.post(
        "/api/translate",
        json={"source_language": "en", "target_language": "ta", "text": "Hello"},
    )
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"].lower()


def test_history_retrieval(client, mock_provider):
    client.post(
        "/api/translate",
        json={"source_language": "en", "target_language": "ta", "text": "Hello"},
    )
    response = client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


def test_history_deletion(client, mock_provider):
    create = client.post(
        "/api/translate",
        json={"source_language": "en", "target_language": "ta", "text": "Hello"},
    )
    history_id = create.json()["history_id"]
    delete = client.delete(f"/api/history/{history_id}")
    assert delete.status_code == 204
    listing = client.get("/api/history")
    ids = [item["id"] for item in listing.json()["items"]]
    assert history_id not in ids
