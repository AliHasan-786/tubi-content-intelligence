import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Data
    raw_csv_path: str = os.getenv("RAW_CSV_PATH", "Tubi-Data.csv")
    persona_csv_path: str = os.getenv("PERSONA_CSV_PATH", "Tubi_with_Personas_and_Clusters.csv")
    clean_csv_path: str = os.getenv("CLEAN_CSV_PATH", "data/clean_titles.csv")

    # Embeddings cache
    embeddings_npy_path: str = os.getenv("EMBEDDINGS_NPY_PATH", "data/embeddings.npy")
    embeddings_meta_path: str = os.getenv("EMBEDDINGS_META_PATH", "data/embeddings_meta.json")
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

    # LLM API gateway (preferred — OpenAI-compatible proxy)
    llmapi_key: str = os.getenv("LLMAPI_KEY", "")
    llmapi_base_url: str = os.getenv("LLMAPI_BASE_URL", "https://internal.llmapi.ai/v1/chat/completions")
    llmapi_model: str = os.getenv("LLMAPI_MODEL", "gpt-4o-mini")

    # OpenAI (fallback)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Gemini (fallback)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # Telemetry (local JSONL logs; fine for demo + single instance)
    events_log_path: str = os.getenv("EVENTS_LOG_PATH", "data/events.jsonl")

    # CORS for local dev / separate frontend deploys.
    cors_allow_origins: str = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")


settings = Settings()

