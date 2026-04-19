# Copyright (c) 2026, Erick W.R. and contributors
# See license.txt

import io
import json
import os
import shutil
import tarfile
import tempfile
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_typst.utils.print_format import (
    _extract_main_typ_from_tar,
    _extract_source_from_html,
    _get_typst_source,
    build_typst_context,
    get_print_format_template,
    pdf_generator,
)

MINIMAL_TYPST = "#set page(width: 100pt, height: 50pt)\nHello from Typst"


def _make_print_format(typst_type=True, html=MINIMAL_TYPST):
    """Return a mock Print Format doc-like object."""
    return frappe._dict(
        print_format_type="Typst" if typst_type else "Jinja",
        html=html,
        custom_format=1,
        pdf_generator="typst" if typst_type else "wkhtmltopdf",
    )


class TestGetTypstSource(FrappeTestCase):
    def test_returns_html_field_content(self):
        pf = _make_print_format(html="  #strong[Hi]  ")
        source_type, source_data = _get_typst_source(pf)
        self.assertEqual(source_type, "inline")
        self.assertEqual(source_data, "#strong[Hi]")

    def test_returns_empty_string_when_html_blank(self):
        pf = _make_print_format(html="")
        source_type, source_data = _get_typst_source(pf)
        self.assertEqual(source_type, "inline")
        self.assertEqual(source_data, "")

    def test_returns_empty_string_when_html_none(self):
        pf = _make_print_format(html=None)
        source_type, source_data = _get_typst_source(pf)
        self.assertEqual(source_type, "inline")
        self.assertEqual(source_data, "")


class TestExtractSourceFromHtml(FrappeTestCase):
    def test_extracts_between_markers(self):
        html = "<!-- typst-source-start -->#let x = 1<!-- typst-source-end -->"
        self.assertEqual(_extract_source_from_html(html), "#let x = 1")

    def test_returns_none_when_no_markers(self):
        self.assertIsNone(
            _extract_source_from_html("<html><body>No markers</body></html>")
        )

    def test_extracts_multiline_source(self):
        source = "#set page()\n#strong[test]\n"
        html = f"<!-- typst-source-start -->{source}<!-- typst-source-end -->"
        self.assertEqual(_extract_source_from_html(html), source)


class TestGetPrintFormatTemplate(FrappeTestCase):
    def test_returns_none_for_non_typst_format(self):
        pf = _make_print_format(typst_type=False)
        jenv = frappe.get_jenv()
        self.assertIsNone(get_print_format_template(jenv=jenv, print_format=pf))

    def test_returns_none_when_print_format_is_none(self):
        jenv = frappe.get_jenv()
        self.assertIsNone(get_print_format_template(jenv=jenv, print_format=None))

    def test_returns_template_for_typst_format(self):
        pf = _make_print_format()
        jenv = frappe.get_jenv()
        self.assertIsNotNone(get_print_format_template(jenv=jenv, print_format=pf))

    def test_rendered_template_contains_source_and_markers(self):
        pf = _make_print_format(html="#strong[Invoice]")
        jenv = frappe.get_jenv()
        template = get_print_format_template(jenv=jenv, print_format=pf)
        rendered = template.render({})
        self.assertIn("<!-- typst-source-start -->", rendered)
        self.assertIn("<!-- typst-source-end -->", rendered)
        self.assertIn("#strong[Invoice]", rendered)

    def test_jinja_does_not_process_typst_characters(self):
        """Typst '#' and '{}' must not be interpreted by Jinja."""
        pf = _make_print_format(html="#let x = { 1 + 2 }")
        jenv = frappe.get_jenv()
        template = get_print_format_template(jenv=jenv, print_format=pf)
        rendered = template.render({})
        self.assertIn("#let x = { 1 + 2 }", rendered)


class TestPdfGeneratorHook(FrappeTestCase):
    def setUp(self):
        super().setUp()
        # Isolate form_dict so stale doctype/name from other tests don't leak in
        frappe.local.form_dict.update({"doctype": "", "name": "", "format": ""})

    def test_returns_none_for_non_typst_generator(self):
        result = pdf_generator(
            print_format=None,
            html="<html>test</html>",
            options={},
            output=None,
            pdf_generator="wkhtmltopdf",
        )
        self.assertIsNone(result)

    def test_returns_pdf_bytes_for_minimal_typst(self):
        source = "#set page(width: 100pt, height: 50pt)\nHello"
        html = f"<!-- typst-source-start -->{source}<!-- typst-source-end -->"
        result = pdf_generator(
            print_format=None, html=html, options={}, output=None, pdf_generator="typst"
        )
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF"), "Result must be a valid PDF")

    def test_appends_to_existing_pdf_writer(self):
        from pypdf import PdfWriter

        source = "#set page(width: 100pt, height: 50pt)\nPage 1"
        html = f"<!-- typst-source-start -->{source}<!-- typst-source-end -->"
        result = pdf_generator(
            print_format=None,
            html=html,
            options={},
            output=PdfWriter(),
            pdf_generator="typst",
        )
        self.assertIsInstance(result, PdfWriter)
        self.assertGreaterEqual(len(result.pages), 1)

    def test_throws_when_source_not_found(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            pdf_generator(
                print_format=None,
                html="<html>no markers here</html>",
                options={},
                output=None,
                pdf_generator="typst",
            )


class TestBuildTypstContext(FrappeTestCase):
    def test_sys_inputs_all_values_are_strings(self):
        sys_inputs, _ = build_typst_context()
        for key, value in sys_inputs.items():
            self.assertIsInstance(value, str, f"sys_inputs['{key}'] must be str")

    def test_sys_inputs_contains_expected_keys(self):
        sys_inputs, _ = build_typst_context()
        for key in (
            "doctype",
            "docname",
            "print_format_name",
            "language",
            "lh_name",
            "lh_logo_url",
        ):
            self.assertIn(key, sys_inputs)

    def test_extra_files_contains_required_json_files(self):
        _, extra_files = build_typst_context()
        for name in ("doc.json", "user.json", "letterhead.json"):
            self.assertIn(name, extra_files)
            self.assertIsInstance(extra_files[name], bytes)

    def test_doc_json_round_trips(self):
        _, extra_files = build_typst_context()
        parsed = json.loads(extra_files["doc.json"])
        self.assertIsInstance(parsed, dict)

    def test_user_json_has_required_fields(self):
        _, extra_files = build_typst_context()
        user = json.loads(extra_files["user.json"])
        for field in ("name", "full_name", "email", "roles"):
            self.assertIn(field, user)
        self.assertIsInstance(user["roles"], list)

    def test_letterhead_json_empty_when_no_letterhead(self):
        _, extra_files = build_typst_context(no_letterhead=True)
        lh = json.loads(extra_files["letterhead.json"])
        self.assertEqual(lh, {})

    def test_letterhead_sys_inputs_empty_when_no_letterhead(self):
        sys_inputs, _ = build_typst_context(no_letterhead=True)
        self.assertEqual(sys_inputs["lh_name"], "")
        self.assertEqual(sys_inputs["lh_logo_url"], "")

    def test_doc_json_uses_doc_fields_when_doc_provided(self):
        doc = frappe.get_doc("Print Settings")
        sys_inputs, extra_files = build_typst_context(doc=doc)
        parsed = json.loads(extra_files["doc.json"])
        self.assertEqual(parsed.get("doctype"), "Print Settings")
        self.assertEqual(sys_inputs["doctype"], "Print Settings")

    def test_pdf_generator_hook_injects_doc_json(self):
        """End-to-end: template that reads doc.json compiles to valid PDF."""
        source = (
            "#set page(width: 120pt, height: 60pt)\n"
            '#let d = json("doc.json")\n'
            '#d.at("name", default: "")'
        )
        html = f"<!-- typst-source-start -->{source}<!-- typst-source-end -->"
        result = pdf_generator(
            print_format=None, html=html, options={}, output=None, pdf_generator="typst"
        )
        self.assertTrue(result.startswith(b"%PDF"))

    def test_pdf_generator_hook_injects_user_json(self):
        """End-to-end: template that reads user.json compiles to valid PDF."""
        source = (
            "#set page(width: 120pt, height: 60pt)\n"
            '#let u = json("user.json")\n'
            '#u.at("name", default: "")'
        )
        html = f"<!-- typst-source-start -->{source}<!-- typst-source-end -->"
        result = pdf_generator(
            print_format=None, html=html, options={}, output=None, pdf_generator="typst"
        )
        self.assertTrue(result.startswith(b"%PDF"))

    def test_multi_pdf_merge_page_count(self):
        """Two single-page Typst PDFs merged into one writer produce 2 pages."""
        from pypdf import PdfWriter

        source = "#set page(width: 100pt, height: 50pt)\nA"
        html = f"<!-- typst-source-start -->{source}<!-- typst-source-end -->"

        writer = PdfWriter()
        writer = pdf_generator(
            print_format=None,
            html=html,
            options={},
            output=writer,
            pdf_generator="typst",
        )
        writer = pdf_generator(
            print_format=None,
            html=html,
            options={},
            output=writer,
            pdf_generator="typst",
        )
        self.assertEqual(len(writer.pages), 2)


class TestGetTypstSourceFilesystem(FrappeTestCase):
    """Tests for _get_typst_source filesystem resolution (Phase 3)."""

    def setUp(self):
        super().setUp()
        self.tmpdir = tempfile.mkdtemp()
        self.pf = frappe._dict(
            print_format_type="Typst",
            html="inline content",
            module="Accounts",
            name="Test Invoice",
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        super().tearDown()

    def _patches(self, is_custom=0):
        """Return context managers that redirect module path to tmpdir."""
        return [
            patch(
                "frappe_typst.utils.print_format.frappe.get_module_path",
                return_value=self.tmpdir,
            ),
            patch(
                "frappe_typst.utils.print_format.frappe.get_cached_value",
                return_value=is_custom,
            ),
        ]

    # --- inline fallback ---

    def test_inline_fallback_when_no_files(self):
        with self._patches()[0], self._patches()[1]:
            source_type, source_data = _get_typst_source(self.pf)
        self.assertEqual(source_type, "inline")
        self.assertEqual(source_data, "inline content")

    def test_returns_inline_for_none_print_format(self):
        source_type, source_data = _get_typst_source(None)
        self.assertEqual(source_type, "inline")
        self.assertEqual(source_data, "")

    def test_no_module_falls_back_to_inline(self):
        pf = frappe._dict(html="inline", module=None, name="X")
        source_type, source_data = _get_typst_source(pf)
        self.assertEqual(source_type, "inline")

    # --- .typ file priority ---

    def test_typ_file_takes_priority_over_html(self):
        typ_path = os.path.join(self.tmpdir, "test_invoice.typ")
        with open(typ_path, "w", encoding="utf-8") as f:
            f.write("#strong[From file]")

        with self._patches()[0], self._patches()[1]:
            source_type, source_data = _get_typst_source(self.pf)

        self.assertEqual(source_type, "typ")
        self.assertEqual(source_data, typ_path)

    # --- .tar.gz priority ---

    def _write_tar_gz(self, content: bytes = b"#strong[From archive]") -> str:
        tar_path = os.path.join(self.tmpdir, "test_invoice.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            info = tarfile.TarInfo(name="main.typ")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        return tar_path

    def test_tar_gz_takes_priority_over_typ_and_html(self):
        # Both .typ and .tar.gz present — .tar.gz wins
        with open(os.path.join(self.tmpdir, "test_invoice.typ"), "w") as f:
            f.write("#strong[From .typ]")
        tar_path = self._write_tar_gz()

        with self._patches()[0], self._patches()[1]:
            source_type, source_data = _get_typst_source(self.pf)

        self.assertEqual(source_type, "tar.gz")
        self.assertEqual(source_data, tar_path)

    # --- _extract_main_typ_from_tar ---

    def test_extract_main_typ_from_tar(self):
        expected = "#strong[Hello from archive]"
        tar_path = self._write_tar_gz(expected.encode("utf-8"))
        content = _extract_main_typ_from_tar(tar_path)
        self.assertEqual(content, expected)

    def test_extract_main_typ_raises_when_missing(self):
        tar_path = os.path.join(self.tmpdir, "empty.tar.gz")
        with tarfile.open(tar_path, "w:gz"):
            pass  # empty archive — no main.typ

        with self.assertRaises(frappe.exceptions.ValidationError):
            _extract_main_typ_from_tar(tar_path)

    # --- end-to-end: file-based .typ compiles to PDF ---

    def test_pdf_generator_compiles_typ_file(self):
        source = "#set page(width: 100pt, height: 50pt)\n#strong[From .typ file]"
        typ_path = os.path.join(self.tmpdir, "test_invoice.typ")
        with open(typ_path, "w", encoding="utf-8") as f:
            f.write(source)

        pf = frappe._dict(
            print_format_type="Typst",
            html="",
            module="Accounts",
            name="Test Invoice",
        )
        # Provide matching HTML content so the fallback branch also works
        html_with_markers = (
            f"<!-- typst-source-start -->{source}<!-- typst-source-end -->"
        )

        with self._patches()[0], self._patches()[1]:
            result = pdf_generator(
                print_format=pf,
                html=html_with_markers,
                options={},
                output=None,
                pdf_generator="typst",
            )

        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF"))

    # --- end-to-end: .tar.gz archive compiles to PDF ---

    def test_pdf_generator_compiles_tar_gz_archive(self):
        source = "#set page(width: 100pt, height: 50pt)\n#strong[From archive]"
        tar_path = self._write_tar_gz(source.encode("utf-8"))

        pf = frappe._dict(
            print_format_type="Typst",
            html="",
            module="Accounts",
            name="Test Invoice",
        )
        html_with_markers = (
            f"<!-- typst-source-start -->{source}<!-- typst-source-end -->"
        )

        with self._patches()[0], self._patches()[1]:
            result = pdf_generator(
                print_format=pf,
                html=html_with_markers,
                options={},
                output=None,
                pdf_generator="typst",
            )

        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF"))
