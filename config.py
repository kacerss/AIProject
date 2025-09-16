from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass(frozen=True)
class Settings:
    demo_password: str = os.getenv("APP_DEMO_PASSWORD", "changeme")
    embed_model: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    data_dir: Path = Path(os.getenv("DATA_DIR", "./data")).resolve()
    db_path: Path = Path(os.getenv("DB_PATH", "./data/rag_app.db")).resolve()
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "50"))

settings = Settings()  # <-- THIS is the object you're importing
settings.data_dir.mkdir(parents=True, exist_ok=True)
