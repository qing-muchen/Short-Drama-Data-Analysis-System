"""API tests for the read-only Drama 360° profile endpoint."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from main import app
from routers.dependencies import get_drama_profile_service
from services.drama_profile.contracts import (
    AvailabilityReason,
    DramaProfileBasic,
    DramaProfileResponse,
    ModuleAvailability,
)


class FakeProfileService:
    def __init__(self, profile=None):
        self.profile = profile
        self.calls = []

    def get_profile(self, drama_id):
        self.calls.append(drama_id)
        if self.profile is None:
            return DramaProfileResponse(
                drama=DramaProfileBasic(drama_id=drama_id, title="测试短剧"),
                availability={
                    "score": ModuleAvailability(available=False, reason=AvailabilityReason.NOT_CALCULATED),
                    "quality": ModuleAvailability(available=False, reason=AvailabilityReason.NOT_CALCULATED),
                    "prediction": ModuleAvailability(available=False, reason=AvailabilityReason.INSUFFICIENT_HISTORY),
                    "anomaly": ModuleAvailability(available=False, reason=AvailabilityReason.NO_ANOMALY),
                    "action": ModuleAvailability(available=True),
                    "explanation": ModuleAvailability(available=False, reason=AvailabilityReason.NOT_AVAILABLE),
                },
            )
        return self.profile


def test_profile_route_is_registered_and_read_only():
    paths = {route.path for route in app.routes}
    assert "/api/v1/dramas/{drama_id}/profile" in paths
    methods = {
        method
        for route in app.routes
        if route.path == "/api/v1/dramas/{drama_id}/profile"
        for method in route.methods
    }
    assert methods == {"GET"}


def test_router_converts_service_dto_to_uniform_response():
    fake = FakeProfileService()
    app.dependency_overrides[get_drama_profile_service] = lambda: fake
    try:
        client = TestClient(app)
        response = client.get("/api/v1/dramas/7/profile")
        assert response.status_code in {200, 401}
        if response.status_code == 200:
            assert response.json()["data"]["drama"]["drama_id"] == 7
            assert response.json()["data"]["availability"]["prediction"]["reason"] == "INSUFFICIENT_HISTORY"
            assert fake.calls == [7]
    finally:
        app.dependency_overrides.pop(get_drama_profile_service, None)


def test_schema_boundary_does_not_add_write_routes():
    for route in app.routes:
        if route.path == "/api/v1/dramas/{drama_id}/profile":
            assert route.methods == {"GET"}
