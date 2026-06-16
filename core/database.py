from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime

Base = declarative_base()

# Define the SQL Table Structure
class ReviewLog(Base):
    __tablename__ = "review_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    repo_name = Column(String, index=True)
    pr_number = Column(Integer)
    commit_sha = Column(String)
    file_path = Column(String)
    severity = Column(String, index=True)
    rule_id = Column(String)
    message = Column(Text)
    ai_explanation = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Initialize SQLite Database Connection
engine = create_engine("sqlite:///./reviews.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the file and tables automatically
Base.metadata.create_all(bind=engine)

def save_issues(repo_name: str, pr_number: int, sha: str, issues: list):
    """Takes the LangGraph output and saves it to the local database."""
    db = SessionLocal()
    try:
        for issue in issues:
            log = ReviewLog(
                repo_name=repo_name,
                pr_number=pr_number,
                commit_sha=sha,
                file_path=issue.get("file", ""),
                severity=issue.get("sev", "LOW"),
                rule_id=issue.get("rule", ""),
                message=issue.get("msg", ""),
                ai_explanation=issue.get("ai_note", "")
            )
            db.add(log)
        db.commit()
    except Exception as e:
        print(f"❌ DB Error: {e}")
    finally:
        db.close()