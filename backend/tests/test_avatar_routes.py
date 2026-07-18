from __future__ import annotations

import struct

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.routers import avatar as avatar_router
from app.services import avatar_storage


VALID_GLB_HEADER = b"glTF" + struct.pack("<II", 2, 20) + struct.pack("<II", 0, 0)


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/admin-login", json={"username": "admin", "password": "123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _visitor_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/visitor-register",
        json={"username": "avatar_visitor", "password": "password123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_publish_vrm_and_visitor_only_reads_enabled_variant(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(avatar_storage, "AVATAR_UPLOAD_DIRECTORY", tmp_path / "avatars")
    admin_headers = _admin_headers(client)

    scenic_response = client.post(
        "/api/admin/scenic-areas",
        headers=admin_headers,
        json={"code": "avatar-test", "name": "Avatar Test Scenic Area"},
    )
    assert scenic_response.status_code == 201
    scenic_area = scenic_response.json()

    human_response = client.post(
        "/api/admin/avatars/humans",
        headers=admin_headers,
        json={
            "name": "Test Guide",
            "gender": "female",
            "role_title": "Scenic Culture Guide",
            "tts_voice": "Cherry",
            "tts_instructions": "Speak clearly and warmly.",
        },
    )
    assert human_response.status_code == 201
    human = human_response.json()

    upload_response = client.post(
        "/api/admin/avatars/variants",
        headers=admin_headers,
        data={
            "digital_human_id": str(human["id"]),
            "scenic_area_id": str(scenic_area["id"]),
            "outfit_name": "Light Green New Chinese Style",
            "version": "v1",
            "is_enabled": "true",
            "is_default": "true",
            "sort_order": "0",
        },
        files={"file": ("guide.vrm", VALID_GLB_HEADER, "model/gltf-binary")},
    )
    assert upload_response.status_code == 201
    avatar = upload_response.json()
    assert avatar["is_enabled"] is True
    assert avatar["is_default"] is True

    visitor_headers = _visitor_headers(client)
    visible_response = client.get("/api/avatars/scenic-areas/avatar-test", headers=visitor_headers)
    assert visible_response.status_code == 200
    visible = visible_response.json()
    assert visible["default_variant_id"] == avatar["id"]
    assert [item["id"] for item in visible["avatars"]] == [avatar["id"]]

    asset_response = client.get(
        f"/api/avatars/scenic-areas/avatar-test/variants/{avatar['id']}/asset",
        headers=visitor_headers,
    )
    assert asset_response.status_code == 200
    assert asset_response.content.startswith(b"glTF")
    assert asset_response.headers["accept-ranges"] == "bytes"
    assert asset_response.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert asset_response.headers["etag"]

    cached_response = client.get(
        f"/api/avatars/scenic-areas/avatar-test/variants/{avatar['id']}/asset",
        headers={**visitor_headers, "If-None-Match": asset_response.headers["etag"]},
    )
    assert cached_response.status_code == 304
    assert cached_response.content == b""

    range_response = client.get(
        f"/api/avatars/scenic-areas/avatar-test/variants/{avatar['id']}/asset",
        headers={**visitor_headers, "Range": "bytes=0-3"},
    )
    assert range_response.status_code == 206
    assert range_response.content == b"glTF"
    assert range_response.headers["content-range"] == f"bytes 0-3/{len(VALID_GLB_HEADER)}"

    disable_response = client.patch(
        f"/api/admin/avatars/scenic-configs/{avatar['config_id']}",
        headers=admin_headers,
        json={"is_enabled": False},
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["is_default"] is False

    hidden_response = client.get("/api/avatars/scenic-areas/avatar-test", headers=visitor_headers)
    assert hidden_response.status_code == 200
    assert hidden_response.json()["avatars"] == []
    assert client.get(
        f"/api/avatars/scenic-areas/avatar-test/variants/{avatar['id']}/asset",
        headers=visitor_headers,
    ).status_code == 404


def test_invalid_vrm_is_rejected_without_creating_a_variant(client: TestClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(avatar_storage, "AVATAR_UPLOAD_DIRECTORY", tmp_path / "avatars")
    admin_headers = _admin_headers(client)
    scenic = client.post(
        "/api/admin/scenic-areas",
        headers=admin_headers,
        json={"code": "invalid-avatar", "name": "Invalid Avatar Scenic Area"},
    ).json()
    human = client.post(
        "/api/admin/avatars/humans",
        headers=admin_headers,
        json={
            "name": "Invalid Upload Guide",
            "gender": "male",
            "role_title": "Test Guide",
            "tts_voice": "Cherry",
        },
    ).json()

    response = client.post(
        "/api/admin/avatars/variants",
        headers=admin_headers,
        data={
            "digital_human_id": str(human["id"]),
            "scenic_area_id": str(scenic["id"]),
            "outfit_name": "Invalid Outfit",
        },
        files={"file": ("not-vrm.vrm", b"not-a-glb", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert client.get(
        "/api/admin/avatars/scenic-configs",
        headers=admin_headers,
        params={"scenic_area_id": scenic["id"]},
    ).json() == []
    assert not (tmp_path / "avatars").exists()


def test_upload_validation_and_database_failure_do_not_leave_vrm_files(client: TestClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(avatar_storage, "AVATAR_UPLOAD_DIRECTORY", tmp_path / "avatars")
    admin_headers = _admin_headers(client)
    scenic = client.post(
        "/api/admin/scenic-areas",
        headers=admin_headers,
        json={"code": "cleanup-avatar", "name": "Cleanup Avatar Scenic Area"},
    ).json()
    human = client.post(
        "/api/admin/avatars/humans",
        headers=admin_headers,
        json={
            "name": "Cleanup Upload Guide",
            "gender": "female",
            "role_title": "Test Guide",
            "tts_voice": "Cherry",
        },
    ).json()

    blank_name_response = client.post(
        "/api/admin/avatars/variants",
        headers=admin_headers,
        data={
            "digital_human_id": str(human["id"]),
            "scenic_area_id": str(scenic["id"]),
            "outfit_name": "   ",
        },
        files={"file": ("guide.vrm", VALID_GLB_HEADER, "model/gltf-binary")},
    )
    assert blank_name_response.status_code == 422
    assert not (tmp_path / "avatars").exists()

    def fail_config_creation(*args, **kwargs):
        raise SQLAlchemyError("simulated database failure")

    monkeypatch.setattr(avatar_router, "create_scenic_avatar_config", fail_config_creation)
    failed_save_response = client.post(
        "/api/admin/avatars/variants",
        headers=admin_headers,
        data={
            "digital_human_id": str(human["id"]),
            "scenic_area_id": str(scenic["id"]),
            "outfit_name": "Clean Outfit",
        },
        files={"file": ("guide.vrm", VALID_GLB_HEADER, "model/gltf-binary")},
    )
    assert failed_save_response.status_code == 500
    assert list((tmp_path / "avatars").glob("*.vrm")) == []
    assert client.get(
        "/api/admin/avatars/scenic-configs",
        headers=admin_headers,
        params={"scenic_area_id": scenic["id"]},
    ).json() == []
