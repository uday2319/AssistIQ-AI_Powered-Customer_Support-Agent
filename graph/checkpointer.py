"""
Where LangGraph saves conversations.

- "postgres" (default): saved in PostgreSQL, so chats and pending
  refund approvals survive restarts and work across several
  Cloud Run instances.
- "memory": saved in RAM only. Used by tests and quick experiments.
  Everything is lost when the process stops.

Choose with the CHECKPOINT_BACKEND setting.
"""

from langgraph.checkpoint.memory import MemorySaver

from config import CHECKPOINT_BACKEND
from db.connection import connection_info


def create_checkpointer():
    if CHECKPOINT_BACKEND == "memory":
        return MemorySaver()

    if CHECKPOINT_BACKEND != "postgres":
        raise ValueError(
            f"Unknown CHECKPOINT_BACKEND '{CHECKPOINT_BACKEND}'. "
            "Use 'postgres' or 'memory'."
        )

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    # A pool reuses a few open connections instead of opening
    # a new one for every message.
    pool = ConnectionPool(
        conninfo=connection_info(),
        min_size=1,
        max_size=10,
        # Settings required by PostgresSaver.
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=True,
    )

    checkpointer = PostgresSaver(pool)

    # Creates LangGraph's tables the first time. Safe to run every start.
    checkpointer.setup()

    return checkpointer
