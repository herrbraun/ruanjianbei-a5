from __future__ import annotations

from fastapi.testclient import TestClient

from app.routers import media


def test_runtime_upload_directory_is_not_public(client: TestClient) -> None:
    knowledge_response = client.get(
        "/uploads/knowledge/f320d4677a6e6af7_灵山胜境%20景点结构化数据集.docx"
    )
    vrm_response = client.get("/uploads/avatars/021b501e7e9447aeac541580407df537.vrm")

    assert knowledge_response.status_code == 404
    assert vrm_response.status_code == 404


def test_generated_user_avatar_remains_public(client: TestClient, tmp_path, monkeypatch) -> None:
    avatar_name = "user-1-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png"
    avatar_file = tmp_path / avatar_name
    avatar_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(media, "USER_AVATAR_DIRECTORY", tmp_path)

    response = client.get(f"/uploads/avatars/{avatar_name}")

    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n\x1a\n"
