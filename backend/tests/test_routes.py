from __future__ import annotations

from fastapi.testclient import TestClient


def auth_headers(client: TestClient, path: str, username: str, password: str) -> dict[str, str]:
    response = client.post(path, json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_spot(client: TestClient, headers: dict[str, str], *, scenic_area: str, name: str) -> int:
    response = client.post(
        "/api/admin/spots",
        headers=headers,
        json={
            "scenic_area": scenic_area,
            "name": name,
            "summary": f"{name}简介",
            "description": f"{name}详细介绍",
            "recommended_duration_minutes": 30,
            "priority": 10,
            "tags": ["文化"],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_recommendation_never_mixes_scenic_areas(client: TestClient) -> None:
    admin_headers = auth_headers(client, "/api/auth/admin-login", "admin", "123456")
    lingshan_id = create_spot(client, admin_headers, scenic_area="灵山胜境", name="灵山测试景点")
    nianhuawan_id = create_spot(client, admin_headers, scenic_area="拈花湾禅意小镇", name="拈花湾测试景点")
    register = client.post(
        "/api/auth/visitor-register",
        json={"username": "routevisitor", "password": "password123"},
    )
    visitor_headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    response = client.post(
        "/api/routes/recommend",
        headers=visitor_headers,
        json={
            "scenic_area": "灵山胜境",
            "interest": "文化",
            "duration_minutes": 60,
            "preference": "balanced",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["scenic_area"] == "灵山胜境"
    assert lingshan_id in {item["spot_id"] for item in payload["spots"]}
    assert nianhuawan_id not in {item["spot_id"] for item in payload["spots"]}


def test_route_rejects_start_spot_from_another_scenic_area(client: TestClient) -> None:
    admin_headers = auth_headers(client, "/api/auth/admin-login", "admin", "123456")
    create_spot(client, admin_headers, scenic_area="灵山胜境", name="灵山起点测试")
    other_area_id = create_spot(client, admin_headers, scenic_area="拈花湾禅意小镇", name="错误跨区起点")
    register = client.post(
        "/api/auth/visitor-register",
        json={"username": "startvisitor", "password": "password123"},
    )
    visitor_headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    response = client.post(
        "/api/routes/recommend",
        headers=visitor_headers,
        json={
            "scenic_area": "灵山胜境",
            "interest": "文化",
            "duration_minutes": 60,
            "start_spot_id": other_area_id,
            "preference": "balanced",
        },
    )

    assert response.status_code == 400
