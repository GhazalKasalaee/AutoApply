"""
Central configuration. Loads environment variables and project paths.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model config
GEMINI_MODEL = "gemini-3.1-flash-lite"  # Fast & free-tier friendly

# Paths
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = PROJECT_ROOT / "autoapply.db"
CV_PATH = DATA_DIR / "my_cv.txt"

# Make sure data dir exists
DATA_DIR.mkdir(exist_ok=True)