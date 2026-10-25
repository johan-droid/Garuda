"""Visitor bookmarks: save, list and remove the places someone pinned.

These endpoints carry no authentication, because there is no account to
authenticate. They are scoped instead by an opaque, client-generated id sent
in `X-Client-Id`, which is what keeps one visitor's bookmarks out of another's
list. The id is meaningless to the server beyond being a namespace: it is
never derived from, or joined to, anything else.

Three rules shape the responses:

  * Saving is idempotent. The same place saved twice yields one row and no
    error, so a retry after a dropped connection cannot double a bookmark.
  * The stored place round-trips whole. The chip needs the name and the map
    needs the coordinates, so a bookmark that came back as an id alone would
    not be the bookmark that was saved.
  * Deleting something that is not there is a 404, not a success. A silent
    success would let a client believe it removed a bookmark it never had.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.session import get_db
from app.domain.contracts import Place
from app.models.saved_place import SavedPlaceModel

router = APIRouter(prefix="/saved-places", tags=["saved-places"])

SessionDep = Annotated[Session, Depends(get_db)]
ClientIdDep = Annotated[
    str,
    Header(
        min_length=8,
        max_length=64,
        alias="X-Client-Id",
        description="Opaque, client-generated identifier that namespaces the bookmarks",
    ),
]
PlaceIdPath = Annotated[
    str,
    Path(min_length=1, max_length=64, description="Stable place identifier"),
]


@router.get("", response_model=list[Place], summary="List saved places")
def list_saved_places(session: SessionDep, client_id: ClientIdDep) -> list[Place]:
    """Return the caller's saved places, oldest first."""
    rows = session.scalars(
        select(SavedPlaceModel)
        .where(SavedPlaceModel.owner_id == client_id)
        .order_by(SavedPlaceModel.created_at, SavedPlaceModel.place_id)
    ).all()
    return [Place.model_validate_json(row.place_data) for row in rows]


@router.post("", response_model=Place, status_code=status.HTTP_201_CREATED, summary="Save a place")
def save_place(place: Place, session: SessionDep, response: Response, client_id: ClientIdDep) -> Place:
    """Save a place for the caller, or refresh it if it is already saved."""
    payload = place.model_dump_json()
    existing = session.get(SavedPlaceModel, (client_id, place.id))
    if existing is not None:
        # Already saved: report it as such rather than as a new row, and take
        # the chance to store what the client now holds - a bookmark that
        # never refreshed would keep a name the upstream has since changed.
        if existing.place_data != payload:
            existing.place_data = payload
            session.commit()
        response.status_code = status.HTTP_200_OK
        return place
    # ponytail: check-then-insert, so two concurrent saves of one place can
    # race to an IntegrityError on this single SQLite deployment; the
    # composite primary key still holds, the loser would see a 500. Move to
    # an ON CONFLICT upsert if that ever shows up.
    session.add(SavedPlaceModel(owner_id=client_id, place_id=place.id, place_data=payload))
    session.commit()
    return place


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a saved place")
def delete_place(place_id: PlaceIdPath, session: SessionDep, client_id: ClientIdDep) -> None:
    """Remove one of the caller's saved places."""
    row = session.get(SavedPlaceModel, (client_id, place_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Place '{place_id}' is not saved by this client",
        )
    session.delete(row)
    session.commit()
