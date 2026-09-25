from db.connection import get_connection


def find_order(order_id: str,customer_id:str) -> dict | None:
    """
    Find an order only if it belongs to the authenticated customer.

    Why:
    Knowing an order ID should NOT automatically give access
    to that order.
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
                    expected_delivery,
                    delivered_at
                FROM orders
                WHERE order_id = %s
                AND customer_id=%s;
                """,
                (order_id,customer_id)
            )

            order = cursor.fetchone()

            if order is None:
                return None

            
            return {
                "order_id": order[0],
                "customer_id": order[1],
                "status": order[2],
                "expected_delivery": order[3],
                "delivered_at": order[4]
            }

    except Exception as e:
        print(f"Database error: {e}")

        raise
    finally:
        
        connection.close()

def cancel_order(order_id: str,customer_id:str) -> dict | None:
    """
    Cancel an order only if:
    1. The order belongs to the authenticated customer.
    2. The order is currently cancellable.

    customer_id comes from trusted application state,
    not from Gemini.
    """


    connection = get_connection()

    try:
        with connection.cursor() as cursor:

        
            cursor.execute(
    """
    UPDATE orders
    SET status = 'cancelled'
    WHERE order_id = %s
    AND custome_id=%s
      AND status IN ('pending', 'processing')
    RETURNING
        order_id,
        customer_id,
        status,
        expected_delivery,
        delivered_at;
    """,
    (order_id,customer_id)
)

            order = cursor.fetchone()

    
            if order is None:
                return None

            cursor.execute(
                    """
                    SELECT order_id, customer_id, status
                    FROM orders
                    WHERE order_id = %s
                    """,
                    (order_id,)
                )
            if order is None:
                    return {
                        "success": False,
                        "code": "ORDER_NOT_FOUND",
                        "message": "Order not found."
                    }

            if order[1] != customer_id:
                    return {
                        "success": False,
                        "code": "ORDER_NOT_ACCESSIBLE",
                        "message": "Order not found or not accessible."
                    }

            return {
                    "success": False,
                    "code": "ORDER_NOT_CANCELLABLE",
                    "message": "This order cannot be cancelled."
                }
            
        connection.commit()

        return {
                "order_id": order[0],
                "customer_id": order[1],
                "status": "cancelled",
                "expected_delivery": order[3],
                "delivered_at": order[4],
                "message": "Order cancelled successfully."
            }

    except Exception as e:
        
        connection.rollback()

        print(f"Database error: {e}")
        raise

    finally:
        connection.close()