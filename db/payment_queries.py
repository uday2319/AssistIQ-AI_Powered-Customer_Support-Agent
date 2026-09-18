from db.connection import get_connection

def find_payment(order_id: str) -> dict | None:
    """
    Find the payment associated with an order.

    Returns payment information if found.
    Returns None if no payment exists.
    """
    connection= get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                 """
                SELECT
                    payment_id,
                    order_id,
                    amount,
                    payment_status,
                    payment_method
                FROM payments
                WHERE order_id = %s;
                """,
                (order_id,)
            )

            payment=cursor.fetchone()

            if payment is None:
                return None

            
            return {
                "payment_id": payment[0],
                "order_id": payment[1],
                "amount": float(payment[2]),
                "payment_status": payment[3],
                "payment_method": payment[4]
            }

    except Exception as e:
        print(f"Database error: {e}")
        raise

    finally:
        connection.close()