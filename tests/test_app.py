from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.app import activities, app


@pytest.fixture(autouse=True)
def isolate_activities():
    snapshot = deepcopy(activities)
    try:
        yield
    finally:
        activities.clear()
        activities.update(snapshot)


@pytest.fixture
def client(isolate_activities):
    with TestClient(app) as test_client:
        yield test_client


def test_root_redirect(client):
    # Arrange
    expected_location = "/static/index.html"

    # Act
    response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == expected_location


def test_get_activities(client):
    # Arrange
    expected_activities = deepcopy(activities)
    expected_fields = {"description", "schedule", "max_participants", "participants"}

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == expected_activities
    assert "Chess Club" in response.json()
    for activity in response.json().values():
        assert expected_fields <= activity.keys()
        assert isinstance(activity["participants"], list)


def test_signup_adds_one_participant(client):
    # Arrange
    activity_name = "Chess Club"
    email = "new@mergington.edu"
    expected_activities = client.get("/activities").json()
    expected_activities[activity_name]["participants"].append(email)

    # Act
    response = client.post(
        f"/activities/{activity_name}/signup", params={"email": email}
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for {activity_name}"}
    assert client.get("/activities").json() == expected_activities


def test_duplicate_signup_leaves_activities_unchanged(client):
    # Arrange
    activity_name = "Chess Club"
    email = "new@mergington.edu"
    client.post(f"/activities/{activity_name}/signup", params={"email": email})
    expected_activities = client.get("/activities").json()

    # Act
    response = client.post(
        f"/activities/{activity_name}/signup", params={"email": email}
    )

    # Assert
    assert response.status_code == 400
    assert response.json() == {"detail": "Student already signed up for this activity"}
    assert client.get("/activities").json() == expected_activities
    assert expected_activities[activity_name]["participants"].count(email) == 1


@pytest.mark.parametrize(
    "method, activity_name, action, detail",
    [
        ("POST", "Unknown Club", "signup", "Activity not found"),
        ("DELETE", "Unknown Club", "unregister", "Activity not found"),
        (
            "DELETE", "Chess Club", "unregister",
            "Student is not signed up for this activity",
        ),
    ],
)
def test_missing_resource_leaves_activities_unchanged(
    client, method, activity_name, action, detail
):
    # Arrange
    email = "not-registered@mergington.edu"
    expected_activities = client.get("/activities").json()

    # Act
    response = client.request(
        method, f"/activities/{activity_name}/{action}", params={"email": email}
    )

    # Assert
    assert response.status_code == 404
    assert response.json() == {"detail": detail}
    assert client.get("/activities").json() == expected_activities


def test_unregister_removes_only_requested_participant(client):
    # Arrange
    activity_name = "Chess Club"
    email = "michael@mergington.edu"
    expected_activities = client.get("/activities").json()
    expected_activities[activity_name]["participants"].remove(email)

    # Act
    response = client.delete(
        f"/activities/{activity_name}/unregister", params={"email": email}
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from {activity_name}"}
    assert client.get("/activities").json() == expected_activities


def test_signup_after_unregister(client):
    # Arrange
    activity_name = "Chess Club"
    email = "returning@mergington.edu"
    client.post(f"/activities/{activity_name}/signup", params={"email": email})
    client.delete(f"/activities/{activity_name}/unregister", params={"email": email})
    expected_activities = client.get("/activities").json()
    expected_activities[activity_name]["participants"].append(email)

    # Act
    response = client.post(
        f"/activities/{activity_name}/signup", params={"email": email}
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for {activity_name}"}
    assert client.get("/activities").json() == expected_activities
    assert expected_activities[activity_name]["participants"].count(email) == 1


@pytest.mark.parametrize("method, action", [("POST", "signup"), ("DELETE", "unregister")])
def test_missing_email_leaves_activities_unchanged(client, method, action):
    # Arrange
    activity_name = "Chess Club"
    expected_activities = client.get("/activities").json()

    # Act
    response = client.request(method, f"/activities/{activity_name}/{action}")

    # Assert
    assert response.status_code == 422
    assert any(
        error["loc"] == ["query", "email"]
        for error in response.json()["detail"]
    )
    assert client.get("/activities").json() == expected_activities