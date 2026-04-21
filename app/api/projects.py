from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Place, Project
from app.schemas import (
    ProjectCreate,
    ProjectListItem,
    ProjectPage,
    ProjectRead,
    ProjectUpdate,
)
from app.services.artic import ArticClient, ArticError, get_artic_client


router = APIRouter(prefix="/projects", tags=["projects"])


async def _get_project_or_404(session: AsyncSession, project_id: int) -> Project:
    project: Project | None = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    artic: ArticClient = Depends(get_artic_client),
) -> Project:
    try:
        payload.validate_places_count()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    external_ids = [p.external_id for p in payload.places]
    if len(external_ids) != len(set(external_ids)):
        raise HTTPException(status_code=422, detail="Duplicate places in request")

    project = Project(
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
    )

    # validate each place against artic before we touch the DB
    for place_in in payload.places:
        try:
            artwork = await artic.get_artwork(place_in.external_id)
        except ArticError:
            raise HTTPException(status_code=502, detail="Art Institute API is unavailable")

        if artwork is None:
            raise HTTPException(
                status_code=422,
                detail=f"Artwork {place_in.external_id} not found in Art Institute API",
            )

        project.places.append(
            Place(
                external_id=place_in.external_id,
                title=artwork.get("title") or f"Artwork #{place_in.external_id}",
                notes=place_in.notes,
            )
        )

    session.add(project)
    await session.commit()
    await session.refresh(project, attribute_names=["places"])
    return project


@router.get("", response_model=ProjectPage)
async def list_projects(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_completed: bool | None = Query(None, description="Filter by completion status"),
    name: str | None = Query(None, description="Case-insensitive substring match on name"),
) -> ProjectPage:
    stmt = select(Project)
    count_stmt = select(func.count()).select_from(Project)

    if is_completed is not None:
        stmt = stmt.filter_by(is_completed=is_completed)
        count_stmt = count_stmt.filter_by(is_completed=is_completed)

    if name:
        pattern = f"%{name.strip()}%"
        stmt = stmt.where(Project.name.ilike(pattern))
        count_stmt = count_stmt.where(Project.name.ilike(pattern))

    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Project.created_at.desc()).limit(limit).offset(offset)
    projects = (await session.scalars(stmt)).all()

    items = [
        ProjectListItem(
            id=p.id,
            name=p.name,
            description=p.description,
            start_date=p.start_date,
            is_completed=p.is_completed,
            created_at=p.created_at,
            places_count=len(p.places),
        )
        for p in projects
    ]
    return ProjectPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> Project:
    return await _get_project_or_404(session, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await _get_project_or_404(session, project_id)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=422, detail="No fields to update")

    for field, value in data.items():
        setattr(project, field, value)

    await session.commit()
    await session.refresh(project, attribute_names=["places"])
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    project = await _get_project_or_404(session, project_id)

    if any(place.is_visited for place in project.places):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete project with visited places",
        )

    await session.delete(project)
    await session.commit()
