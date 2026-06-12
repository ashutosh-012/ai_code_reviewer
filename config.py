from dotenv import load_dotenv
import os

load_dotenv()

class Cfg:
    gh_token = os.getenv("GITHUB_TOKEN", "")
    gh_secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    db_url = os.getenv("DB_URL", "sqlite:///./reviews.db")
    max_comments = int(os.getenv("MAX_COMMENTS", "15"))
    cc_threshold = int(os.getenv("CC_THRESHOLD", "10"))
    fn_length = int(os.getenv("FN_LENGTH", "50"))

cfg = Cfg()