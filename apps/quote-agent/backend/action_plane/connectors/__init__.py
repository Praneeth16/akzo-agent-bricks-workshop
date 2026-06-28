"""Tool connectors — one per external system the Action Plane acts on.

Each connector module exposes `send(payload: dict) -> {ref_id, system, raw, via}`
that maps an action payload to its mock endpoint body and POSTs it through a
governed path (UC HTTP connection `akzo_external_systems`, or SP-direct fallback).

`SYSTEMS` maps a stable connector key → the module, so the executor can dispatch
by name and apps/UI can introspect the available connectors.
"""
from __future__ import annotations

from . import crm, email, erp_po, sharepoint, teams, ticket
from ._http import ConnectorError

SYSTEMS = {
    "email": email,
    "teams": teams,
    "crm": crm,
    "erp_po": erp_po,
    "sharepoint": sharepoint,
    "ticket": ticket,
}

__all__ = [
    "SYSTEMS",
    "ConnectorError",
    "email",
    "teams",
    "crm",
    "erp_po",
    "sharepoint",
    "ticket",
]
