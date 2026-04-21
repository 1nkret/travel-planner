from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.config import settings


class PlaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: int
    title: str
    notes: str | None = None
    is_visited: bool


class PlaceCreate(BaseModel):
    external_id: int = Field(..., description="Artwork ID from the Art Institute of Chicago API")
    notes: str | None = Field(default=None, max_length=2000)


class PlaceUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    is_visited: bool | None = None


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    start_date: date | None = None


class ProjectCreate(ProjectBase):
    places: list[PlaceCreate] = Field(default_factory=list)

    def validate_places_count(self) -> None:
        # kept here instead of Field(min_length=1, max_length=10) so we can share the
        # upper bound from settings and give a clearer message for each case
        if not self.places:
            raise ValueError("Project must contain at least one place")
        if len(self.places) > settings.max_places_per_project:
            raise ValueError(
                f"too many places, max is {settings.max_places_per_project}"
            )


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    start_date: date | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    start_date: date | None
    is_completed: bool
    created_at: datetime
    places: list[PlaceRead]


class ProjectListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    start_date: date | None
    is_completed: bool
    created_at: datetime
    places_count: int


class Page(BaseModel):
    total: int
    limit: int
    offset: int


class ProjectPage(Page):
    items: list[ProjectListItem]
