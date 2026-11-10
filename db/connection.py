import psycopg
from psycopg.conninfo import make_conninfo

from config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD
)

# Give up after this many seconds instead of hanging forever
# when the database cannot be reached.
CONNECT_TIMEOUT_SECONDS = 10


def connection_info() -> str:
    """Build the PostgreSQL connection string from config."""
    return make_conninfo(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
    )


def get_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        return psycopg.connect(connection_info())
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        raise
