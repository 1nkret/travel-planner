from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_basic_auth
from app.config import settings
from app.database import get_session
from app.models import Place, Project
from app.schemas import PlaceCreate, PlaceRead, PlaceUpdate
from app.services.artic import ArticClient, ArticError, get_artic_client


router = APIRouter(
    prefix="/projects/{project_id}/places",
    tags=["places"],
    dependencies=[Depends(require_basic_auth)],
)


async def _load_project(session: AsyncSession, project_id: int) -> Project:
    project: Project | None = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _load_place(session: AsyncSession, project_id: int, place_id: int) -> Place:
    stmt = select(Place).filter_by(id=place_id, project_id=project_id)
    place = (await session.scalars(stmt)).one_or_none()
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    return place


@router.get("", response_model=list[PlaceRead])
async def list_places(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> Sequence[Place]:
    await _load_project(session, project_id)  # 404 if project doesn't exist
    stmt = select(Place).filter_by(project_id=project_id).order_by(Place.id)
    return (await session.scalars(stmt)).all()


@router.get("/{place_id}", response_model=PlaceRead)
async def get_place(
    project_id: int,
    place_id: int,
    session: AsyncSession = Depends(get_session),
) -> Place:
    return await _load_place(session, project_id, place_id)


@router.post("", response_model=PlaceRead, status_code=status.HTTP_201_CREATED)
async def add_place(
    project_id: int,
    payload: PlaceCreate,
    session: AsyncSession = Depends(get_session),
    artic: ArticClient = Depends(get_artic_client),
) -> Place:
    project = await _load_project(session, project_id)

    if len(project.places) >= settings.max_places_per_project:
        raise HTTPException(
            status_code=409,
            detail=f"Project already has {settings.max_places_per_project} places",
        )

    # checking here so we can return a clean 409 instead of leaking the DB constraint
    if any(p.external_id == payload.external_id for p in project.places):
        raise HTTPException(status_code=409, detail="Place already added to this project")

    try:
        artwork = await artic.get_artwork(payload.external_id)
    except ArticError:
        raise HTTPException(status_code=502, detail="Art Institute API is unavailable")

    if artwork is None:
        raise HTTPException(
            status_code=422,
            detail=f"Artwork {payload.external_id} not found in Art Institute API",
        )

    place = Place(
        project_id=project.id,
        external_id=payload.external_id,
        title=artwork.get("title") or f"Artwork #{payload.external_id}",
        notes=payload.notes,
    )
    session.add(place)
    await session.commit()
    await session.refresh(place)
    return place


@router.patch("/{place_id}", response_model=PlaceRead)
async def update_place(
    project_id: int,
    place_id: int,
    payload: PlaceUpdate,
    session: AsyncSession = Depends(get_session),
) -> Place:
    place = await _load_place(session, project_id, place_id)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=422, detail="No fields to update")

    for field, value in data.items():
        setattr(place, field, value)

    # auto-complete the project when every place is visited
    if "is_visited" in data:
        stmt = select(Place).filter_by(project_id=project_id)
        all_places = (await session.scalars(stmt)).all()
        project = await _load_project(session, project_id)
        project.is_completed = bool(all_places) and all(p.is_visited for p in all_places)

    await session.commit()
    await session.refresh(place)
    return place
