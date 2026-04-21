from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travel"
    redis_url: str = "redis://localhost:6379/0"

    artic_base_url: str = "https://api.artic.edu/api/v1"
    artic_cache_ttl: int = 3600  # seconds

    max_places_per_project: int = 10


settings = Settings()
