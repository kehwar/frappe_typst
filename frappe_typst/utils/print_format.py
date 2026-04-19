"""
Typst Print Format integration for Frappe.

Hooks:
  - get_print_format_template: wraps Typst source in {% raw %} so Jinja never
    processes '#', '{', '}' characters.  Returns a Jinja template whose
    rendered output is the original Typst source embedded in HTML comment
    markers ready for extraction by the pdf_generator hook.
  - pdf_generator: extracts the Typst source from the HTML comment markers
    (or reloads from the filesystem for file-based formats), builds the full
    data context via build_typst_context(), compiles via TypstBuilder, and
    returns PDF bytes.

Data context:
  sys_inputs carries str-only scalar metadata.  Structured data is injected
  as virtual JSON files (doc.json, user.json, letterhead.json) via
  builder.files so templates can access full document and session data.

Source resolution:
  For standard (non-custom-module) print formats, _get_typst_source checks the
  module filesystem path for a .tar.gz archive or a .typ file before falling
  back to the html field, mirroring Frappe's .html convention.

Jinja pre-processing:
  Before compilation, .typ and inline sources are rendered through
  frappe.utils.jinja.render_template (safe_render=False — trusted app source,
  avoids false positives on Typst's ".__" patterns).

  Context variables available in every .typ template:
    doc         — full document dict (same data as doc.json)
    user        — current user dict (same data as user.json)
    letterhead  — letter head dict (same data as letterhead.json)
    get_doc     — get_doc(doctype, name) → dict  (wraps frappe.get_cached_doc)

  Frappe's Jinja env globals (get_safe_globals) are also available, including
  html2text(), frappe.utils.date_diff(), frappe.utils.fmt_money(), etc.

  .tar.gz archives are passed directly to TypstBuilder without Jinja
  pre-processing; use the Python before_print hook instead for those.
"""

import json as _json
import os
import re

import frappe

_SOURCE_START = "<!-- typst-source-start -->"
_SOURCE_END = "<!-- typst-source-end -->"


# ---------------------------------------------------------------------------
# Hook 1 — get_print_format_template
# ---------------------------------------------------------------------------


def get_print_format_template(jenv, print_format):
    """
    Called by frappe/www/printview.py before standard template rendering.

    Returns a Jinja template that embeds the Typst source verbatim inside
    HTML comment markers (bypassing Jinja processing via {% raw %}) when
    print_format_type == "Typst".  Returns None for all other formats so
    Frappe falls through to its default rendering.

    For file-based formats (.tar.gz / .typ), the content of main.typ (or the
    .typ file) is embedded so that Frappe's printview produces usable HTML
    that the pdf_generator hook can recognise.
    """
    if not print_format or getattr(print_format, "print_format_type", None) != "Typst":
        return None

    source_type, source_data = _get_typst_source(print_format)

    if source_type == "tar.gz":
        content = _extract_main_typ_from_tar(source_data)
    elif source_type == "typ":
        with open(source_data, encoding="utf-8") as f:
            content = f.read()
    else:
        content = source_data  # inline string

    if not content:
        return None

    # Wrap source in {% raw %}...{% endraw %} so Jinja never interprets
    # '#', '{', '}' that appear in Typst markup.  Surround with comment
    # markers so the pdf_generator hook can extract the source from the
    # full printview HTML.
    wrapper = _SOURCE_START + "{% raw %}" + content + "{% endraw %}" + _SOURCE_END
    return jenv.from_string(wrapper)


# ---------------------------------------------------------------------------
# Hook 2 — pdf_generator
# ---------------------------------------------------------------------------


def pdf_generator(print_format, html, options, output, pdf_generator):
    """
    Called by frappe/utils/print_utils.py when pdf_generator != "wkhtmltopdf".

    Extracts Typst source from HTML comment markers or reloads from the
    filesystem (for .tar.gz / .typ formats), builds the full data context,
    compiles via TypstBuilder, and returns PDF bytes.  Returns None if
    pdf_generator != "typst" so other hooks in the chain can handle it.

    When `output` (a pypdf.PdfWriter) is provided, compiled pages are appended
    to it and the writer is returned instead of raw bytes.
    """
    if pdf_generator != "typst":
        return None

    form_dict = frappe.local.form_dict
    doctype = form_dict.get("doctype")
    docname = form_dict.get("name")
    no_letterhead = frappe.utils.cint(form_dict.get("no_letterhead", 0))
    letterhead_name = form_dict.get("letterhead") or None

    doc = None
    if doctype and docname:
        try:
            doc = frappe.get_doc(doctype, docname)
        except frappe.DoesNotExistError:
            pass
    sys_inputs, extra_files = build_typst_context(
        doc=doc,
        letter_head=letterhead_name,
        no_letterhead=no_letterhead,
    )

    from frappe_typst.utils.typst import TypstBuilder

    builder = TypstBuilder()

    if print_format is not None:
        source_type, source_data = _get_typst_source(print_format)
        if source_type == "tar.gz":
            # tar.gz archives are passed directly — Jinja not applied.
            builder.read_file_path(source_data)
        elif source_type == "typ":
            with open(source_data, encoding="utf-8") as fh:
                raw_source = fh.read()
            builder.read_string(_render_jinja(raw_source, extra_files))
        else:
            # Inline: use html field content, falling back to HTML markers.
            if not source_data:
                source_data = _extract_source_from_html(html) or ""
            if not source_data:
                frappe.throw(
                    frappe._("Typst source not found in print output."),
                    title=frappe._("Typst Print Error"),
                )
            builder.read_string(_render_jinja(source_data, extra_files))
    else:
        # No print_format (test / programmatic mode): extract from HTML markers.
        source = _extract_source_from_html(html)
        if not source:
            frappe.throw(
                frappe._("Typst source not found in print output."),
                title=frappe._("Typst Print Error"),
            )
        builder.read_string(_render_jinja(source, extra_files))

    builder.files.update(extra_files)

    pdf_bytes = builder.compile(format="pdf", sys_inputs=sys_inputs)

    if output is not None:
        try:
            import io

            from pypdf import PdfReader, PdfWriter

            reader = PdfReader(io.BytesIO(pdf_bytes))
            if not isinstance(output, PdfWriter):
                output = PdfWriter()
            for page in reader.pages:
                output.add_page(page)
            return output
        except ImportError:
            pass  # pypdf not available — fall through and return raw bytes

    return pdf_bytes


# ---------------------------------------------------------------------------
# Public API: build_typst_context
# ---------------------------------------------------------------------------


def build_typst_context(
    doc=None,
    letter_head: str | None = None,
    no_letterhead: bool | int = False,
) -> tuple[dict[str, str], dict[str, bytes]]:
    """
    Build the complete Typst data context for a print job.

    Returns:
        sys_inputs: dict[str, str] — scalar metadata for Typst sys.inputs.
            Keys: doctype, docname, print_format_name, language, and
            letterhead scalar fields (lh_name, lh_logo_url).
        extra_files: dict[str, bytes] — virtual JSON files to inject into
            builder.files before compilation.
            - doc.json: full document as dict (frappe.as_json serialised)
            - user.json: current session user (name, full_name, email, roles)
            - letterhead.json: letterhead fields, or {} when no_letterhead

    Templates access context as:
        #let doc = json("doc.json")
        #let user = json("user.json")
        #let lh = json("letterhead.json")
        sys.inputs.doctype, sys.inputs.language, etc.
    """
    form_dict = frappe.local.form_dict

    # --- doc.json ---
    if doc is not None:
        doc_dict = doc.as_dict()
    else:
        # Minimal stub so templates that reference doc.json don't crash
        doc_dict = {
            "name": str(form_dict.get("name") or ""),
            "doctype": str(form_dict.get("doctype") or ""),
        }

    # --- user.json ---
    user_name = frappe.session.user
    user_doc = frappe.get_cached_doc("User", user_name)
    user_data = {
        "name": user_doc.name,
        "full_name": user_doc.full_name or "",
        "email": user_doc.email or "",
        "roles": [r.role for r in (user_doc.roles or [])],
    }

    # --- letterhead.json ---
    lh_data: dict = {}
    lh_name = ""
    lh_logo_url = ""

    if not no_letterhead and letter_head:
        try:
            lh_doc = frappe.get_cached_doc("Letter Head", letter_head)
            lh_data = {
                "name": lh_doc.name,
                "html": lh_doc.content or "",
                "footer": lh_doc.footer or "",
                "logo_url": lh_doc.image or "",
            }
            lh_name = lh_doc.name
            lh_logo_url = lh_doc.image or ""
        except frappe.DoesNotExistError:
            pass

    # --- sys_inputs (str values only) ---
    sys_inputs: dict[str, str] = {
        "doctype": str((doc.doctype if doc else form_dict.get("doctype")) or ""),
        "docname": str((doc.name if doc else form_dict.get("name")) or ""),
        "print_format_name": str(form_dict.get("format") or ""),
        "language": str(frappe.local.lang or ""),
        "lh_name": lh_name,
        "lh_logo_url": lh_logo_url,
    }

    # --- extra_files ---
    extra_files: dict[str, bytes] = {
        "doc.json": frappe.as_json(doc_dict).encode("utf-8"),
        "user.json": frappe.as_json(user_data).encode("utf-8"),
        "letterhead.json": frappe.as_json(lh_data).encode("utf-8"),
    }

    return sys_inputs, extra_files


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _render_jinja(source: str, extra_files: dict[str, bytes]) -> str:
    """
    Render a Typst source string through ``frappe.utils.jinja.render_template``.

    Uses the shared Frappe Jinja environment so all app-registered hooks
    (methods, filters) are available.

    Context variables available in templates:
      doc         — document dict (from doc.json)
      user        — user dict (from user.json)
      letterhead  — letter head dict (from letterhead.json)
      get_doc     — callable: get_doc(doctype, name) → dict, returns {} on error.
                    Templates fetch linked docs on demand:
                    {% set company = get_doc('Company', doc.company) %}
    """
    from frappe.utils.jinja import render_template

    context: dict = {}
    for key in ("doc", "user", "letterhead"):
        fname = f"{key}.json"
        context[key] = _json.loads(extra_files[fname]) if fname in extra_files else {}

    def _get_doc(doctype: str, name: str) -> dict:
        if not name:
            return {}
        try:
            return frappe.get_cached_doc(doctype, name).as_dict()
        except Exception:
            return {}

    context["get_doc"] = _get_doc

    # safe_render=False: Typst source is trusted app code, not user input.
    # Also avoids false positives on ".__" which can appear in Typst syntax.
    return render_template(source, context, safe_render=False)


def _get_typst_source(print_format) -> tuple[str, str]:
    """
    Resolve the Typst source for a print format.

    Returns a (source_type, data) tuple:
      ("tar.gz", "/abs/path")  — .tar.gz archive on the module filesystem
      ("typ",    "/abs/path")  — single .typ file on the module filesystem
      ("inline", "...markup") — html field content (fallback)

    Filesystem sources are only checked for standard (non-custom-module)
    formats that have a module set, mirroring Frappe's .html convention in
    frappe/www/printview.py.  The priority order is: .tar.gz > .typ > html.
    """
    if print_format:
        module = getattr(print_format, "module", None)
        if module:
            base_dir = frappe.get_module_path(module, "Print Format", print_format.name)
            scrubbed = frappe.scrub(print_format.name)

            tar_path = os.path.join(base_dir, scrubbed + ".tar.gz")
            if os.path.exists(tar_path):
                return ("tar.gz", tar_path)

            typ_path = os.path.join(base_dir, scrubbed + ".typ")
            if os.path.exists(typ_path):
                return ("typ", typ_path)

    return (
        "inline",
        (getattr(print_format, "html", None) or "").strip() if print_format else "",
    )


def _extract_main_typ_from_tar(tar_path: str) -> str:
    """Extract the content of main.typ from a .tar.gz Typst archive."""
    import tarfile

    with tarfile.open(tar_path, "r:gz") as tar:
        try:
            member = tar.getmember("main.typ")
        except KeyError:
            frappe.throw(
                frappe._("Typst archive {0} must contain main.typ").format(tar_path),
                title=frappe._("Typst Print Error"),
            )
        f = tar.extractfile(member)
        return f.read().decode("utf-8")


def _extract_source_from_html(html: str) -> str | None:
    """Extract Typst source from the HTML comment markers."""
    pattern = re.compile(
        re.escape(_SOURCE_START) + r"(.*?)" + re.escape(_SOURCE_END),
        re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        return None
    return match.group(1)
