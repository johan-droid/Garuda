"""Saved places: a visitor's bookmarks, scoped to the client that made them.

The app is anonymous by default - no accounts, no cookies - so the only thing
separating one visitor's bookmarks from another's is an opaque client id the
browser sends along. These tests pin that isolation, that saving twice cannot
create two rows, and that deleting something you never saved is a 404 rather
than a silent success.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.saved_place import SavedPlaceModel

OWNER = "11111111-2222-3333-4444-555555555555"
OTHER_OWNER = "99999999-8888-7777-6666-555555555555"

PATH = "/api/v1/saved-places"


@pytest.fixture(autouse=True)
def _fresh_bookmarks(db: Session) -> None:
    """Start each test with nothing saved.

    The schema is created once for the session, and a bookmark outlives the
    request that made it - which is the entire point of the feature - so the
    rows would otherwise leak from one test into the next.
    """
    db.execute(delete(SavedPlaceModel))
    db.commit()


def _place(place_id: str = "IN-OD-29", name: str = "Khordha") -> dict[str, Any]:
    return {
        "id": place_id,
        "canonical_name": name,
        "aliases": ["Khurda"],
        "place_type": "district",
        "parent_id": "IN-OD",
        "coordinates": [20.1833, 85.6022],
        "resolution_method": "census_2011",
        "geometry_available": True,
    }


def _headers(owner: str = OWNER) -> dict[str, str]:
    return {"X-Client-Id": owner}


def test_saving_requires_a_client_id(client: TestClient) -> None:
    """Without an owner there is nothing to scope the bookmark to."""
    assert client.post(PATH, json=_place()).status_code == 422


def test_saving_then_listing_round_trips_the_whole_place(client: TestClient) -> None:
    created = client.post(PATH, json=_place(), headers=_headers())

    assert created.status_code == 201
    assert created.json()["id"] == "IN-OD-29"

    listed = client.get(PATH, headers=_headers())
    assert listed.status_code == 200
    saved = listed.json()
    assert [p["id"] for p in saved] == ["IN-OD-29"]
    # The chip and the map both need more than an id, so what goes in must
    # come back whole.
    assert saved[0] == _place()


def test_saving_the_same_place_twice_is_idempotent(client: TestClient) -> None:
    first = client.post(PATH, json=_place(), headers=_headers())
    second = client.post(PATH, json=_place(), headers=_headers())

    assert (first.status_code, second.status_code) == (201, 200)
    assert len(client.get(PATH, headers=_headers()).json()) == 1


def test_bookmarks_are_scoped_to_the_client_that_made_them(client: TestClient) -> None:
    client.post(PATH, json=_place(), headers=_headers())

    assert client.get(PATH, headers=_headers(OTHER_OWNER)).json() == []
    assert len(client.get(PATH, headers=_headers()).json()) == 1


def test_saving_starts_from_an_empty_list(client: TestClient) -> None:
    assert client.get(PATH, headers=_headers()).json() == []


def test_deleting_a_saved_place_removes_it(client: TestClient) -> None:
    client.post(PATH, json=_place(), headers=_headers())

    deleted = client.delete(f"{PATH}/IN-OD-29", headers=_headers())

    assert deleted.status_code == 204
    assert client.get(PATH, headers=_headers()).json() == []


def test_deleting_an_unknown_place_is_a_404(client: TestClient) -> None:
    assert client.delete(f"{PATH}/IN-OD-29", headers=_headers()).status_code == 404
    # Already gone counts as unknown rather than being quietly re-deleted.
    client.post(PATH, json=_place(), headers=_headers())
    client.delete(f"{PATH}/IN-OD-29", headers=_headers())
    assert client.delete(f"{PATH}/IN-OD-29", headers=_headers()).status_code == 404


def test_deleting_leaves_other_visitors_bookmarks_alone(client: TestClient) -> None:
    client.post(PATH, json=_place(), headers=_headers())

    assert client.delete(f"{PATH}/IN-OD-29", headers=_headers(OTHER_OWNER)).status_code == 404
    assert len(client.get(PATH, headers=_headers()).json()) == 1
