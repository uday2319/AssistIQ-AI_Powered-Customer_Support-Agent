from datetime import date

from utils.policy import REFUND_WINDOW_DAYS


def is_refund_eligible(delivered_at: date | None) -> bool:
    """
    Check whether an order is still within the refund window
    (REFUND_WINDOW_DAYS from policy.yaml).

    Returns True if the customer can request a refund.
    Returns False if the refund window has expired.
    """

    if delivered_at is None:
        return False

    today = date.today()

    days_since_delivery = (today - delivered_at).days
    return 0 <= days_since_delivery <= REFUND_WINDOW_DAYS
