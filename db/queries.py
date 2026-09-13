from db.connection import get_connection


def find_order(order_id: str) -> dict | None:
    """
    Find an order in PostgreSQL using its order ID.

    Returns:
        Order information if found.
        None if the order doesn't exist.
    """

    # Open a connection to PostgreSQL.
    connection = get_connection()

    try: 
        with connection.cursor() as cursor:
             
            cursor.execute(
                """
                SELECT
                    order_id,
                    customer_id,
                    status,
                    expected_delivery
                FROM orders
                WHERE order_id = %s;
                """,
                (order_id,)
            )

            order = cursor.fetchone()

            if order is None:
                return None

            
            return {
                "order_id": order[0],
                "customer_id": order[1],
                "status": order[2],
                "expected_delivery": order[3]
            }

    except Exception as e:
        print(f"Database error: {e}")

        raise
    finally:
        
        connection.close()