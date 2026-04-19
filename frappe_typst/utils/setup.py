# Copyright (c) 2026, Erick W.R. and contributors
# For license information, please see license.txt

"""
Install / uninstall helpers for Typst Print Format field options.

Both functions are idempotent:
  - install: reads the live meta options, appends the Typst entry only if
    it is not already present, then writes the Property Setter.
  - uninstall: reads the live meta options, removes the Typst entry if
    present, then either updates or deletes the Property Setter.
"""

import frappe

# Field specs: (fieldname, entry_to_add)
_FIELD_ENTRIES = [
    ("print_format_type", "Typst"),
    ("pdf_generator", "typst"),
]

_DOCTYPE = "Print Format"


def install():
    """Add Typst options to Print Format select fields (idempotent)."""
    for fieldname, entry in _FIELD_ENTRIES:
        current = _get_current_options(fieldname)
        if entry not in current:
            _save_options(fieldname, current + [entry])


def uninstall():
    """Remove Typst options from Print Format select fields (idempotent)."""
    for fieldname, entry in _FIELD_ENTRIES:
        current = _get_current_options(fieldname)
        if entry in current:
            updated = [o for o in current if o != entry]
            _save_options(fieldname, updated)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_current_options(fieldname: str) -> list[str]:
    """
    Return the current options list for a Print Format select field.

    Priority: live Property Setter → DocType meta field definition.
    Returns a list of non-empty strings.
    """
    ps_name = f"{_DOCTYPE}-{fieldname}-options"
    if frappe.db.exists("Property Setter", ps_name):
        raw = frappe.db.get_value("Property Setter", ps_name, "value") or ""
    else:
        raw = (
            frappe.db.get_value(
                "DocField",
                {"parent": _DOCTYPE, "fieldname": fieldname},
                "options",
            )
            or ""
        )

    return [o for o in raw.splitlines() if o.strip()]


def _save_options(fieldname: str, options: list[str]) -> None:
    """
    Write the updated options list back as a Property Setter.

    If the resulting list matches the original DocField definition exactly,
    the Property Setter is deleted (no override needed).
    """
    from frappe.custom.doctype.property_setter.property_setter import (
        make_property_setter,
    )

    base_raw = (
        frappe.db.get_value(
            "DocField",
            {"parent": _DOCTYPE, "fieldname": fieldname},
            "options",
        )
        or ""
    )
    base_options = [o for o in base_raw.splitlines() if o.strip()]

    ps_name = f"{_DOCTYPE}-{fieldname}-options"

    if options == base_options:
        # Back to default — remove the Property Setter if it exists
        if frappe.db.exists("Property Setter", ps_name):
            frappe.delete_doc("Property Setter", ps_name, ignore_permissions=True)
        return

    make_property_setter(
        doctype=_DOCTYPE,
        fieldname=fieldname,
        property="options",
        value="\n".join(options),
        property_type="Text",
        validate_fields_for_doctype=False,
    )
