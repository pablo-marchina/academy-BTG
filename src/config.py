from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Groq / LLM
    GROQ_API_KEY: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # ANBIMA — suporta tanto API Key simples quanto OAuth2 (client_id/secret/access_token)
    ANBIMA_API_KEY: str = ""
    ANBIMA_CLIENT_ID: str = ""
    ANBIMA_CLIENT_SECRET: str = ""
    ANBIMA_ACCESS_TOKEN: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Pipeline
    SCORE_THRESHOLD: float = 65.0
    DATE_LOOKBACK_DAYS: int = 30
    REQUEST_TIMEOUT: int = 60

    # Storage
    SQLITE_PATH: str = "data/btg_intelligence.db"
    QDRANT_PATH: str = "data/qdrant"
    PDF_STORAGE_PATH: str = "data/pdfs"

    # URLs base
    ANBIMA_BASE_URL: str = "https://api.anbima.com.br"
    CVM_BASE_URL: str = "https://dados.cvm.gov.br"
    BCB_BASE_URL: str = "https://api.bcb.gov.br"

    @property
    def anbima_token_ativo(self) -> str:
        """Retorna o melhor token ANBIMA disponível."""
        return self.ANBIMA_ACCESS_TOKEN or self.ANBIMA_API_KEY or ""

    @property
    def anbima_configurada(self) -> bool:
        """True se qualquer credencial ANBIMA estiver configurada."""
        return bool(
            self.ANBIMA_ACCESS_TOKEN
            or self.ANBIMA_API_KEY
            or self.ANBIMA_CLIENT_ID
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    LOG_FILE: str = "logs/btg_intelligence.log"
    LOG_LEVEL: str = "INFO"

    def setup_dirs(self) -> None:
        """Cria diretórios de storage se não existirem."""
        for p in [self.PDF_STORAGE_PATH, self.QDRANT_PATH, Path(self.LOG_FILE).parent]:
            Path(p).mkdir(parents=True, exist_ok=True)
        Path(self.SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
