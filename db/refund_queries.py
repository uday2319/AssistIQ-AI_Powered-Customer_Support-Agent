from db.connection import get_connection

def find_refund(payment_id: str) -> dict | None:
    """
    Find an existing refund for a payment.

    Returns refund information if a refund exists.
    Returns None if no refund exists.
    """

    
    connection = get_connection()

    try:
        
        with connection.cursor() as cursor:

        
            cursor.execute(
                """
                SELECT
                    refund_id,
                    payment_id,
                    amount,
                    refund_status
                FROM refunds
                WHERE payment_id = %s;
                """,
                (payment_id,)
            )

        
            refund = cursor.fetchone()

            
            if refund is None:
                return None

            
            return {
                "refund_id": refund[0],
                "payment_id": refund[1],
                "amount": float(refund[2]),
                "refund_status": refund[3]
            }

    except Exception as e:
        
        print(f"Database error: {e}")
        raise

    finally:
    
        connection.close()
        
def create_refund(
    refund_id: str,
    payment_id: str,
    amount: float
) -> dict:
    """
    Create a new refund record in PostgreSQL.
    """

    
    connection = get_connection()

    try:
        
        with connection.cursor() as cursor:

            
            cursor.execute(
                """
                INSERT INTO refunds (
                    refund_id,
                    payment_id,
                    amount,
                    refund_status
                )
                VALUES (%s, %s, %s, %s);
                """,
                (
                    refund_id,
                    payment_id,
                    amount,
                    "processed"
                )
            )

            
            connection.commit()

            
            return {
                "refund_id": refund_id,
                "payment_id": payment_id,
                "amount": amount,
                "refund_status": "processed"
            }

    except Exception as e:
    
        connection.rollback()

        print(f"Database error: {e}")
        raise

    finally:
        
        connection.close()