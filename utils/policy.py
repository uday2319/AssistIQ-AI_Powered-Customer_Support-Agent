"""
Loads policy.yaml, the single source of truth for store rules,
and generates the knowledge-base documents from it.

After editing policy.yaml, regenerate the documents:
    python -m utils.policy
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
POLICY_FILE = ROOT / "policy.yaml"
KNOWLEDGE_BASE_DIR = ROOT / "knowledge_base"


def _load() -> dict:
    with POLICY_FILE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


POLICY = _load()

REFUND_WINDOW_DAYS: int = POLICY["refund"]["window_days"]
ALLOWED_REFUND_REASONS: dict[str, str] = POLICY["refund"]["allowed_reasons"]
REFUNDABLE_PAYMENT_STATUSES: tuple[str, ...] = tuple(POLICY["refund"]["refundable_payment_statuses"])
REFUND_PROCESSING_TIME: str = POLICY["refund"]["processing_time"]
CANCELLABLE_STATUSES: tuple[str, ...] = tuple(POLICY["cancellation"]["cancellable_statuses"])


# ------------------------------------------------------------------
# Rule sentences. Used in BOTH the documents and the refusal
# messages, so customers see the exact same wording everywhere.
# ------------------------------------------------------------------

def _or_list(items) -> str:
    """'a', 'a or b', 'a, b, or c'"""
    items = list(items)
    if len(items) <= 2:
        return " or ".join(items)
    return ", ".join(items[:-1]) + ", or " + items[-1]


RULES = {
    "refund_window": (
        f"Customers can request a refund within {REFUND_WINDOW_DAYS} days "
        "of receiving their order."
    ),
    "refund_reasons": (
        "Refunds are available only when "
        + _or_list(ALLOWED_REFUND_REASONS.values())
        + ". Refunds are not available if the customer simply changed their mind."
    ),
    "refund_delivered_only": "Refunds can be requested only after the order has been delivered.",
    "refund_paid_only": "Only orders that were paid successfully can be refunded.",
    "refund_once": "Orders that have already been refunded cannot be refunded again.",
    "refund_timing": (
        f"Once a refund is approved, it is normally processed within {REFUND_PROCESSING_TIME}."
    ),
    "refund_destination": f"Refunds are returned to {POLICY['refund']['paid_to']}.",
    "cancel_before_shipping": (
        "Customers can cancel an order only before it has been shipped "
        f"(while it is {_or_list(CANCELLABLE_STATUSES)})."
    ),
    "cancel_after_shipping": (
        "Once an order has been shipped, it cannot be cancelled. The customer can wait "
        "for delivery and then request a refund according to the refund policy."
    ),
    "cancel_needs_order_id": "Cancellation requests should include the customer's order ID.",
    "standard_delivery": (
        f"Standard delivery normally takes {POLICY['shipping']['standard_delivery']}."
    ),
    "express_delivery": (
        f"Express delivery normally takes {POLICY['shipping']['express_delivery']}."
    ),
    "order_status": "Customers can check their order status using their order ID.",
    "delivery_delays": (
        "Delivery dates may change because of weather, logistics problems, "
        "or other unexpected delays."
    ),
}


def policy_documents() -> dict[str, str]:
    """The knowledge-base files, built from the rules above."""

    def document(title, rule_names):
        return title + "\n\n" + "\n\n".join(RULES[name] for name in rule_names) + "\n"

    return {
        "refund_policy.txt": document("Refund Policy", [
            "refund_window", "refund_reasons", "refund_delivered_only", "refund_paid_only",
            "refund_once", "refund_timing", "refund_destination",
        ]),
        "cancellation_policy.txt": document("Cancellation Policy", [
            "cancel_before_shipping", "cancel_after_shipping", "cancel_needs_order_id",
        ]),
        "shipping_policy.txt": document("Shipping Policy", [
            "standard_delivery", "express_delivery", "order_status", "delivery_delays",
        ]),
    }


def write_policy_documents():
    for name, text in policy_documents().items():
        (KNOWLEDGE_BASE_DIR / name).write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    write_policy_documents()
    print("Knowledge-base documents regenerated from policy.yaml:")
    for name in policy_documents():
        print(f"  knowledge_base/{name}")
