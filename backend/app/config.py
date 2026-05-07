import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    OPENAI_API_KEY: str = Field(default='')
    OPENAI_MODEL: str = Field(default='gpt-4o')
    ADMIN_API_KEY: str = Field(default='')

    # Database
    DATABASE_PATH: str = Field(default=str(BASE_DIR / 'hukuk_ai.db'))

    DATA_DIR: str = Field(default=str(BASE_DIR / 'mydata'))
    CHROMA_DB_DIR: str = Field(default=str(BASE_DIR / 'chroma_db'))
    CHROMA_COLLECTION_NAME: str = Field(default='turkish_law_assistant')

    # Yargıtay decisions
    YARGITAY_DIR: str = Field(default=str(BASE_DIR / 'yargıtaykarar'))
    YARGITAY_COLLECTION_NAME: str = Field(default='yargitay_kararlari')
    ANALYSIS_TOP_K: int = Field(default=10)
    EXTRACTION_MODEL: str = Field(default='gpt-4o-mini')

    EMBEDDING_MODEL_NAME: str = Field(default='intfloat/multilingual-e5-base')
    EMBEDDING_DEVICE: str = Field(default='cpu')

    CHUNK_SIZE: int = Field(default=800)
    CHUNK_OVERLAP: int = Field(default=100)
    TOP_K: int = Field(default=15)
    SIMILARITY_THRESHOLD: float = Field(default=0.70)

    TEMPERATURE: float = Field(default=0.2)
    NO_CONTEXT_MESSAGE: str = Field(default='Bu konuda veri bulunamad\u0131.')
    CHAT_STREAM_TIMEOUT_SECONDS: int = Field(default=90)

    LOG_LEVEL: str = Field(default='INFO')

    @field_validator('SIMILARITY_THRESHOLD')
    @classmethod
    def validate_similarity_threshold(cls, value: float) -> float:
        return max(0.0, min(value, 1.0))


settings = Settings()


def ensure_directories() -> None:
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
