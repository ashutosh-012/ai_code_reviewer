import importlib
import os

try:
    load_dotenv = importlib.import_module("dotenv").load_dotenv
except Exception:
    def load_dotenv(dotenv_path=".env", override=False):
        try:
            if hasattr(dotenv_path, "read_text"):
                dotenv_path = str(dotenv_path)
            if not os.path.isfile(dotenv_path):
                return False
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if override or k not in os.environ:
                            os.environ[k] = v
            return True
        except Exception:
            return False

load_dotenv()

class Cfg:
    gh_token = os.getenv("GITHUB_TOKEN", "")
    gh_secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    db_url = os.getenv("DB_URL", "sqlite:///./reviews.db")
    max_comments = int(os.getenv("MAX_COMMENTS", "15"))
    cc_threshold = int(os.getenv("CC_THRESHOLD", "10"))
    fn_length = int(os.getenv("FN_LENGTH", "50"))

cfg = Cfg()