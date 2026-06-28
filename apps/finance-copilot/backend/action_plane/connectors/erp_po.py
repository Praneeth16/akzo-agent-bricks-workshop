"""ERP purchase-order connector → mock `POST /erp/po`
(body: supplier, sku, qty, amount_eur)."""
from __future__ import annotations

from typing import Any

from . import _http

SYSTEM = "erp_po"
PATH = "/erp/po"


def send(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an action payload to the ERP purchase-order endpoint and POST it.

    Accepts `supplier`, `sku`/`material`, `qty`/`quantity`, and
    `amount_eur`/`spend_eur` as the order value.
    """
    supplier = payload.get("supplier") or payload.get("vendor") or "Unknown supplier"
    sku = payload.get("sku") or payload.get("material") or "SKU-UNKNOWN"
    qty = int(payload.get("qty") or payload.get("quantity") or 0)
    amount = float(payload.get("amount_eur") or payload.get("spend_eur") or 0.0)
    return _http.post(
        SYSTEM, PATH,
        {"supplier": supplier, "sku": sku, "qty": qty, "amount_eur": amount},
    )
