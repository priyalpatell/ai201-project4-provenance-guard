import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = "llama-3.3-70b-versatile"
LOG_FILE = "logs/audit_log.db"
VALID_ATTRIBUTIONS = {"likely AI-generated", "uncertain", "likely human-written"}