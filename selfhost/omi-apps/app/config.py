import os


class Settings:
    def __init__(self) -> None:
        self.redis_url: str = os.getenv("OMI_APPS_REDIS_URL", "redis://redis:6379/2")
        self.llm_base_url: str = (
            os.getenv("OMI_APPS_LLM_BASE_URL", "") or os.getenv("OPENAI_BASE_URL", "")
        ).rstrip("/")
        self.llm_api_key: str = os.getenv("OMI_APPS_LLM_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        self.llm_model: str = (
            os.getenv("OMI_APPS_LLM_MODEL", "")
            or os.getenv("OMI_MAIN_MODEL", "")
            or "gpt-4o-mini"
        )
        self.fallback_llm_base_url: str = os.getenv("OMI_APPS_FALLBACK_LLM_BASE_URL", "").rstrip("/")
        self.fallback_llm_api_key: str = os.getenv("OMI_APPS_FALLBACK_LLM_API_KEY", "")
        self.fallback_llm_model: str = os.getenv("OMI_APPS_FALLBACK_LLM_MODEL", "")
        try:
            self.llm_timeout_seconds: float = float(os.getenv("OMI_APPS_LLM_TIMEOUT", "75"))
        except ValueError:
            self.llm_timeout_seconds = 75.0
        self.analysis_min_new_words: int = int(os.getenv("OMI_APPS_ANALYSIS_MIN_WORDS", "40"))
        self.analysis_interval_seconds: int = int(os.getenv("OMI_APPS_ANALYSIS_INTERVAL", "120"))
        self.backend_url: str = (
            os.getenv("OMI_APPS_BACKEND_URL", "") or os.getenv("BASE_API_URL", "")
        ).rstrip("/")
        self.admin_key: str = os.getenv("ADMIN_KEY", "")
        self.notify_on_insight: bool = os.getenv("OMI_APPS_NOTIFY_INSIGHTS", "true").strip().lower() == "true"
        self.notify_min_gap_seconds: int = int(os.getenv("OMI_APPS_NOTIFY_GAP", "60"))
        self.audio_store_dir: str = os.getenv("OMI_APPS_AUDIO_DIR", "/data/audio")


settings = Settings()
