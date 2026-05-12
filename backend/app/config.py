from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    flex_base_url: str = "https://clearlamp.flexrentalsolutions.com/f5/api/v2"
    flex_username: str = ""
    flex_password: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # How many seconds to cache the full inventory list before re-fetching
    inventory_cache_ttl: int = 300
    # Confidence threshold below which a match is flagged for review
    review_threshold: float = 0.85

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
