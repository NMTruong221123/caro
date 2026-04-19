from backend.services.db_service import init_db_if_missing
from config.settings import DB_PATH


def init_db() -> None:
    init_db_if_missing()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DB_PATH}")
