import os


class Settings:
    def __init__(self) -> None:
        self.redis_url: str = os.getenv("OMI_APPS_REDIS_URL", "redis://redis:6379/2")
        self.llm_base_url: str = os.getenv("OMI_APPS_LLM_BASE_URL", "").rstrip("/")
        self.llm_api_key: str = os.getenv("OMI_APPS_LLM_API_KEY", "")
        self.llm_model: str = os.getenv("OMI_APPS_LLM_MODEL", "")
        self.fallback_llm_base_url: str = os.getenv("OMI_APPS_FALLBACK_LLM_BASE_URL", "").rstrip("/")
        self.fallback_llm_api_key: str = os.getenv("OMI_APPS_FALLBACK_LLM_API_KEY", "")
        self.fallback_llm_model: str = os.getenv("OMI_APPS_FALLBACK_LLM_MODEL", "")
        self.audio_store_dir: str = os.getenv("OMI_APPS_AUDIO_DIR", "/data/audio")


settings = Settings()
