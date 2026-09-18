from datetime import date


def is_refund_eligible(delivered_at: date | None) -> bool:
    """
    Check whether an order is still within the 7-day refund window.

    Returns True if the customer can request a refund.
    Returns False if the refund window has expired.
    """

    if delivered_at is None:
        return False

    today = date.today()

    days_since_delivery = (today - delivered_at).days
    return 0 <= days_since_delivery <= 7