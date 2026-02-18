import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from urllib.parse import urlparse, parse_qs

# Cloud SQL configuration
CLOUD_SQL_CONNECTION_NAME = os.getenv("CLOUD_SQL_CONNECTION_NAME", "elite-hold-485510-t5:europe-west9:lvmh-pipeline-prod")
DB_USER = os.getenv("DB_USER", "lvmh_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "lvmh")

# Check if we should use Cloud SQL
USE_CLOUD_SQL = os.getenv("USE_CLOUD_SQL", "false").lower() == "true"

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Use DATABASE_URL from environment (Cloud Run secrets)
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    # For psycopg2 with unix socket, we need to parse and extract the host
    if "unix_socket" in SQLALCHEMY_DATABASE_URL or "/cloudsql/" in SQLALCHEMY_DATABASE_URL:
        # Parse the URL to extract components
        parsed = urlparse(SQLALCHEMY_DATABASE_URL)
        query_params = parse_qs(parsed.query)
        
        # Extract unix_socket path if present
        unix_socket = query_params.get('host', [None])[0]
        if unix_socket and '/cloudsql/' in unix_socket:
            # Convert to psycopg2 compatible format
            from sqlalchemy import event
            # Remove the query parameter and use unix_socket in connect_args
            SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{parsed.username}:{parsed.password}@/{parsed.path.lstrip('/')}?host={unix_socket}"
elif USE_CLOUD_SQL and CLOUD_SQL_CONNECTION_NAME:
    # Cloud SQL via Unix socket - pg8000 format
    SQLALCHEMY_DATABASE_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_NAME}?unix_socket=/cloudsql/{CLOUD_SQL_CONNECTION_NAME}"
else:
    # Default to SQLite or env var
    SQLALCHEMY_DATABASE_URL = "sqlite:///./lvmh.db"

engine_kwargs = {"pool_pre_ping": True}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Add unix_socket support for psycopg2
    if "/cloudsql/" in SQLALCHEMY_DATABASE_URL:
        parsed = urlparse(SQLALCHEMY_DATABASE_URL)
        query_params = parse_qs(parsed.query)
        unix_socket = query_params.get('host', [None])[0]
        if unix_socket:
            engine_kwargs["connect_args"] = {
                "host": unix_socket
            }
            # Remove host from URL query string
            base_url = f"{parsed.scheme}://{parsed.username}:{parsed.password}@{parsed.netloc.split('@')[1]}{parsed.path}"
            SQLALCHEMY_DATABASE_URL = base_url
    
    engine_kwargs.update(
        {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
        }
    )

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
