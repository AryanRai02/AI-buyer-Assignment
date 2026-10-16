"""
Application configuration and environment settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    BASE_DIR: Path = BASE_DIR
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto").lower()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Purchasing Governance Thresholds
    AUTO_APPROVAL_BUDGET_LIMIT: float = float(os.getenv("AUTO_APPROVAL_BUDGET_LIMIT", "5000.0"))
    MAX_EXPEDITED_PRICE_SURCHARGE_PCT: float = float(os.getenv("MAX_EXPEDITED_PRICE_SURCHARGE_PCT", "25.0"))
    TARGET_SAFETY_STOCK_DAYS: float = 3.0


settings = Settings()
