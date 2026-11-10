"""
Queue of refunds waiting for a support agent.

The paused conversation itself is saved by LangGraph. This table is a
simple list staff can browse, plus a record of each decision.
"""

from db.connection import get_connection

_table_ready = False


def ensure_table():
    """Create the table the first time it's needed."""
    global _table_ready

    if _table_ready:
        return

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS refund_approvals (
                    conversation_id TEXT PRIMARY KEY,
                    customer_id     TEXT NOT NULL,
                    order_id        TEXT NOT NULL,
                    payment_id      TEXT NOT NULL,
                    amount          NUMERIC(10, 2) NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    requested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                    decided_at      TIMESTAMPTZ
                );

                -- Added later: why the customer wants the refund.
                ALTER TABLE refund_approvals ADD COLUMN IF NOT EXISTS reason TEXT;
                ALTER TABLE refund_approvals ADD COLUMN IF NOT EXISTS reason_details TEXT;
                """
            )
        connection.commit()
        _table_ready = True
    finally:
        connection.close()


def add_pending(
    conversation_id: str,
    customer_id: str,
    order_id: str,
    payment_id: str,
    amount: float,
    reason: str | None = None,
    reason_details: str | None = None,
):
    """
    Put a refund in the queue. Safe to call more than once:
    if it's already pending, nothing changes.
    """
    ensure_table()

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO refund_approvals
                    (conversation_id, customer_id, order_id, payment_id, amount,
                     reason, reason_details)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (conversation_id) DO UPDATE SET
                    customer_id    = EXCLUDED.customer_id,
                    order_id       = EXCLUDED.order_id,
                    payment_id     = EXCLUDED.payment_id,
                    amount         = EXCLUDED.amount,
                    reason         = EXCLUDED.reason,
                    reason_details = EXCLUDED.reason_details,
                    status       = 'pending',
                    decided_at   = NULL,
                    -- keep the original time if it was already waiting
                    requested_at = CASE
                        WHEN refund_approvals.status = 'pending'
                        THEN refund_approvals.requested_at
                        ELSE now()
                    END;
                """,
                (conversation_id, customer_id, order_id, payment_id, amount,
                 reason, reason_details),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_pending() -> list[dict]:
    """All refunds waiting for a decision, oldest first."""
    ensure_table()

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT conversation_id, customer_id, order_id,
                       payment_id, amount, requested_at,
                       reason, reason_details
                FROM refund_approvals
                WHERE status = 'pending'
                ORDER BY requested_at;
                """
            )
            return [
                {
                    "conversation_id": row[0],
                    "customer_id": row[1],
                    "order_id": row[2],
                    "payment_id": row[3],
                    "amount": float(row[4]),
                    "requested_at": row[5].isoformat(),
                    "reason": row[6],
                    "reason_details": row[7],
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def mark_decided(conversation_id: str, decision: str):
    """Record the staff decision ("approved" or "rejected")."""
    ensure_table()

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE refund_approvals
                SET status = %s, decided_at = now()
                WHERE conversation_id = %s;
                """,
                (decision, conversation_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
