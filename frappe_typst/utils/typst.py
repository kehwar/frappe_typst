"""
Typst utilities for compiling Typst markup to PDF/PNG/SVG.

This module provides helpers to work with Typst, a markup-based typesetting system.

The TypstBuilder class allows you to:
- Load files from file paths, Frappe File documents, or strings
- Support multi-file projects with multiple files
- Compile to PDF, PNG, or SVG formats
- Save compiled output as Frappe File documents
- Set frappe.response for direct HTTP responses
- Pass dynamic values to templates

Whitelisted API methods:
- generate(): Compile tar.gz archive to PDF/PNG/SVG via HTTP endpoint
"""

import base64
import gzip
import io
import json
import os
import tarfile
from pathlib import Path
from typing import Any, Literal, Optional, Union

import frappe
import typst


class TypstBuilder:
    """
    Helper class to compile Typst files and save as Frappe Files.

    Supports loading files from file paths, Frappe File documents, or strings,
    and compiling to PDF, PNG, or SVG formats. Files are stored internally
    as a dict mapping filenames to bytes content.

    Usage:
        # From file path
        builder = TypstBuilder()
        builder.read_file_path("template.typ")
        builder.compile_and_save("output.pdf")

        # From Frappe File document
        builder = TypstBuilder()
        builder.read_file_doc("FILE-000123")
        builder.compile_and_save("output.pdf")

        # From string
        markup = "#set page(width: 10cm, height: auto)\\n= Hello World!"
        builder = TypstBuilder()
        builder.read_string(markup)
        builder.compile_and_save("output.pdf")

        # With dynamic values and custom template names
        builder = TypstBuilder()
        builder.read_file_path("invoice.typ", name="invoice")
        builder.read_file_path("lib.typ", name="lib")
        builder.compile_and_save(
            "invoice.pdf",
            sys_inputs={"invoice_no": "INV-001", "amount": "1000"}
        )

        # Direct HTTP response (in whitelisted method)
        @frappe.whitelist()
        def my_pdf_endpoint():
            builder = TypstBuilder()
            builder.read_string("= Invoice\\nTotal: $500")
            builder.compile_response(format="pdf", download=True)
    """

    files: dict[str, bytes]  # Internal storage: filename -> bytes content

    def __init__(self):
        """
        Initialize TypstBuilder with empty files.

        Use read_* methods to add files.
        """
        self.files = {}
        self.compiler = typst.Compiler()

    def _normalize_name(self, name: Optional[str]) -> str:
        """
        Normalize file name, adding .typ extension if no extension present.

        Args:
            name: File name or None (defaults to "main.typ")

        Returns:
            Normalized name with extension
        """
        if name is None:
            return "main.typ"

        # Check if name has any extension
        _, ext = os.path.splitext(name)
        if not ext:
            # No extension present, add .typ
            return f"{name}.typ"

        return name

    def read_file_path(
        self, file_path: Union[str, Path], name: Optional[str] = None
    ) -> "TypstBuilder":
        """
        Read a .typ file or .tar.gz/.gz archive from filesystem path and add to files.

        If the file is a gzipped tar archive, all files will be extracted and added to files.
        The archive must contain a main.typ entry point.

        Args:
            file_path: Path to .typ file or .tar.gz/.gz archive
            name: File name (defaults to "main.typ"). Only used for .typ files.
                  Will be normalized to include extension if missing.

        Returns:
            Self for method chaining
        """
        file_path = Path(file_path)
        if not file_path.exists():
            frappe.throw(f"File not found: {file_path}")

        # Check if it's a gzipped tar archive (.tar.gz or .gz)
        if file_path.name.endswith((".tar.gz", ".gz")):
            with tarfile.open(file_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        file_obj = tar.extractfile(member)
                        if file_obj:
                            self.files[member.name] = file_obj.read()

            # Validate main.typ exists
            if "main" not in self.files and "main.typ" not in self.files:
                frappe.throw(
                    "Gzipped tar archive must contain 'main' or 'main.typ' entry point"
                )
            return self

        # Regular .typ file
        if not file_path.suffix == ".typ":
            frappe.throw(
                f"File must have .typ extension or be a gzipped tar archive (.tar.gz or .gz): {file_path}"
            )

        with open(file_path, "rb") as f:
            content = f.read()

        key = self._normalize_name(name)
        self.files[key] = content
        return self

    def read_file_doc(
        self, file_name: str, name: Optional[str] = None
    ) -> "TypstBuilder":
        """
        Read a Frappe File document and add to files.

        If the file is a gzipped tar archive (.tar.gz or .gz), all files will be extracted and added to files.
        The archive must contain a main.typ entry point.

        Args:
            file_name: Name of Frappe File document (e.g., "FILE-000123")
            name: File name (defaults to "main.typ"). Only used for .typ files.
                  Will be normalized to include extension if missing.

        Returns:
            Self for method chaining
        """
        if isinstance(file_name, str):
            file_doc = frappe.get_doc("File", file_name)
        else:
            file_doc = file_name
        file_doc.has_permission("read")

        file_path = file_doc.get_full_path()

        # Delegate to read_file_path
        return self.read_file_path(file_path, name=name)

    def read_string(
        self, markup: Union[str, bytes], name: Optional[str] = None
    ) -> "TypstBuilder":
        """
        Read markup string and add to files.

        Args:
            markup: Typst markup as string or bytes
            name: File name (defaults to "main.typ"). Will be normalized to include extension if missing.

        Returns:
            Self for method chaining
        """
        if isinstance(markup, str):
            content = markup.encode("utf-8")
        else:
            content = markup

        key = self._normalize_name(name)
        self.files[key] = content
        return self

    def read_files(self, files: dict[str, Union[str, bytes, Path]]) -> "TypstBuilder":
        """
        Set multiple files at once from a dict.

        Args:
            files: Dict mapping filenames to content (str/bytes) or file paths
                  Entry point should be keyed as "main" or "main.typ"
                  Example:
                  {
                      "main.typ": b'#import "lib.typ": greet\\n= Hello\\n#greet("World")',
                      "lib.typ": b'#let greet(name) = [Hello, #name!]'
                  }

        Returns:
            Self for method chaining
        """
        if "main" not in files and "main.typ" not in files:
            frappe.throw(
                "Multi-file project must have 'main' or 'main.typ' entry point"
            )

        # Normalize all values to bytes
        normalized_dict = {}
        for key, value in files.items():
            if isinstance(value, str):
                normalized_dict[key] = value.encode("utf-8")
            elif isinstance(value, Path):
                with open(value, "rb") as f:
                    normalized_dict[key] = f.read()
            else:
                normalized_dict[key] = value

        self.files = normalized_dict
        return self

    def compile(
        self,
        format: Literal["pdf", "png", "svg"] = "pdf",
        ppi: Optional[float] = None,
        sys_inputs: Optional[dict[str, str]] = None,
    ) -> bytes:
        """
        Compile Typst files to specified format.

        Args:
            format: Output format - "pdf", "png", or "svg" (default: "pdf")
            ppi: Pixels per inch for PNG output (default: None)
            sys_inputs: Dictionary of values to pass to template
                       Values should be JSON-serializable strings
                       Example: {"name": "John", "items": json.dumps([...])}

        Returns:
            Compiled output as bytes
        """
        compile_kwargs = {
            "input": self.files,
            "format": format,
        }

        if ppi is not None and format == "png":
            compile_kwargs["ppi"] = ppi

        if sys_inputs:
            compile_kwargs["sys_inputs"] = sys_inputs

        try:
            return self.compiler.compile(**compile_kwargs)
        except Exception as e:
            frappe.throw(f"Typst compilation failed: {str(e)}")

    def compile_and_save(
        self,
        output_filename: str,
        format: Optional[Literal["pdf", "png", "svg"]] = None,
        ppi: Optional[float] = None,
        sys_inputs: Optional[dict[str, str]] = None,
        attached_to_doctype: Optional[str] = None,
        attached_to_name: Optional[str] = None,
        is_private: int = 1,
        folder: str = "Home",
    ) -> "frappe._dict":
        """
        Compile Typst files and save as Frappe File document.

        Args:
            output_filename: Name for the output file (e.g., "invoice.pdf")
            format: Output format - "pdf", "png", or "svg"
                   If None, inferred from output_filename extension
            ppi: Pixels per inch for PNG output (default: None)
            sys_inputs: Dictionary of values to pass to template
            attached_to_doctype: Attach file to this DocType
            attached_to_name: Attach file to this document
            is_private: 1 for private file, 0 for public (default: 1)
            folder: Folder to save file in (default: "Home")

        Returns:
            Frappe File document
        """
        # Infer format from filename extension if not provided
        if format is None:
            ext = os.path.splitext(output_filename)[1].lower().lstrip(".")
            if ext not in ["pdf", "png", "svg"]:
                frappe.throw(
                    f"Cannot infer format from extension: {ext}. "
                    "Please specify format parameter."
                )
            format = ext  # type: ignore

        # Compile markup
        compiled_bytes = self.compile(format=format, ppi=ppi, sys_inputs=sys_inputs)

        # Save as Frappe File
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": output_filename,
                "attached_to_doctype": attached_to_doctype,
                "attached_to_name": attached_to_name,
                "folder": folder,
                "is_private": is_private,
                "content": compiled_bytes,
            }
        )
        file_doc.save(ignore_permissions=True)

        return file_doc

    def save_files_as_tar(
        self,
        output_filename: str,
        attached_to_doctype: Optional[str] = None,
        attached_to_name: Optional[str] = None,
        is_private: int = 1,
        folder: str = "Home",
    ) -> "frappe._dict":
        """
        Save the files dict as a gzipped tar archive.

        Args:
            output_filename: Name for the output file (e.g., "templates.tar.gz" or "templates.gz")
            attached_to_doctype: Attach file to this DocType
            attached_to_name: Attach file to this document
            is_private: 1 for private file, 0 for public (default: 1)
            folder: Folder to save file in (default: "Home")

        Returns:
            Frappe File document
        """
        # Ensure .tar.gz or .gz extension
        if not output_filename.endswith((".tar.gz", ".gz")):
            output_filename = f"{output_filename}.tar.gz"

        # Create tar.gz archive in memory
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            for filename, content in self.files.items():
                # Create TarInfo object
                tarinfo = tarfile.TarInfo(name=filename)
                tarinfo.size = len(content)

                # Add file to archive
                tar.addfile(tarinfo, io.BytesIO(content))

        # Get the tar.gz content
        tar_content = tar_buffer.getvalue()

        # Save as Frappe File
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": output_filename,
                "attached_to_doctype": attached_to_doctype,
                "attached_to_name": attached_to_name,
                "folder": folder,
                "is_private": is_private,
                "content": tar_content,
            }
        )
        file_doc.save(ignore_permissions=True)

        return file_doc

    def query(
        self,
        selector: str,
        field: Optional[str] = None,
        one: bool = False,
    ) -> Any:
        """
        Query elements in the Typst template.

        Args:
            selector: CSS-like selector for elements (e.g., "<note>")
            field: Specific field to extract (e.g., "value")
            one: Return only the first match

        Returns:
            Query results (depends on selector and options)
        """
        try:
            result = typst.query(self.files, selector, field=field, one=one)
            return result
        except Exception as e:
            frappe.throw(f"Typst query failed: {str(e)}")

    def compile_response(
        self,
        format: Literal["pdf", "png", "svg"] = "pdf",
        ppi: Optional[float] = None,
        sys_inputs: Optional[dict[str, str]] = None,
        filename: Optional[str] = None,
        download: bool = False,
    ) -> None:
        """
        Compile Typst files and set frappe.response for download/display.

        Use this method in whitelisted functions to return compiled output
        directly to the HTTP client.

        Args:
            format: Output format - "pdf", "png", or "svg" (default: "pdf")
            ppi: Pixels per inch for PNG output (default: None)
            sys_inputs: Dictionary of values to pass to template
            filename: Output filename (default: "output.{format}")
            download: If True, force download; if False, display inline (default: False)

        Example:
            @frappe.whitelist()
            def generate_invoice(invoice_no):
                builder = TypstBuilder()
                builder.read_file_doc("FILE-000123")
                builder.compile_response(
                    format="pdf",
                    sys_inputs={"invoice_no": invoice_no},
                    filename=f"invoice_{invoice_no}.pdf",
                    download=True
                )
        """
        # Compile
        compiled_bytes = self.compile(format=format, ppi=ppi, sys_inputs=sys_inputs)

        # Set appropriate content-type header
        content_types = {
            "pdf": "application/pdf",
            "png": "image/png",
            "svg": "image/svg+xml",
        }

        # Set response
        frappe.response.filename = filename or f"output.{format}"
        frappe.response.filecontent = compiled_bytes
        frappe.response.content_type = content_types.get(
            format, "application/octet-stream"
        )
        frappe.response.type = "download" if download else "asset"


def build(
    raw: Optional[Union[str, bytes]] = None,
    doc: Optional[str] = None,
    path: Optional[Union[str, Path]] = None,
    files: Optional[dict[str, Union[str, bytes, Path]]] = None,
) -> TypstBuilder:
    """
    Convenience function to build a TypstBuilder with a file loaded.

    Provide one of: raw, doc, files, or path parameters.

    Args:
        raw: Typst markup as string or bytes (calls read_string)
        doc: Frappe File document name (e.g., "FILE-000123") (calls read_file_doc)
        files: Dict of multiple files (calls read_files)
        path: Filesystem path to .typ file (calls read_file_path)

    Returns:
        TypstBuilder instance with template loaded

    Example:
        # From string
        builder = build(raw="#set page(width: 10cm, height: auto)\\n= Invoice\\nTotal: $500")
        file_doc = builder.compile_and_save("invoice.pdf")

        # From Frappe File document
        builder = build(doc="FILE-000123")
        file_doc = builder.compile_and_save("output.pdf")

        # From filesystem path
        builder = build(path="template.typ")
        file_doc = builder.compile_and_save("output.pdf")

        # With dynamic values
        builder = build(raw="= Invoice #sys.inputs.invoice_no\\nAmount: $#sys.inputs.amount")
        file_doc = builder.compile_and_save(
            "invoice.pdf",
            sys_inputs={"invoice_no": "INV-001", "amount": "1000"},
            attached_to_doctype="Sales Invoice",
            attached_to_name="INV-001"
        )

        # Direct HTTP response
        @frappe.whitelist()
        def my_endpoint():
            builder = build(doc="FILE-000123")
            builder.compile_response(format="pdf")
    """
    builder = TypstBuilder()

    # Load template based on provided parameter
    if raw is not None:
        builder.read_string(raw)
    elif doc is not None:
        builder.read_file_doc(doc)
    elif path is not None:
        builder.read_file_path(path)
    elif files is not None:
        builder.read_files(files)
    else:
        frappe.throw("Must provide one of: raw, doc, path, or files parameters")

    return builder


@frappe.whitelist()
def generate(
    file: str,
    format: Literal["pdf", "png", "svg"] = "pdf",
    ppi: Optional[float] = None,
    sys_inputs: Optional[dict[str, str]] = None,
    download=None,
):
    """
    Compile a Typst gzipped tar archive File document to specified format and return as response.

    This is a whitelisted API endpoint that can be called via HTTP.

    Args:
        file: File document name (e.g., "FILE-000123") containing a gzipped tar archive (.tar.gz or .gz)
        format: Output format - "pdf", "png", or "svg" (default: "pdf")
        ppi: Pixels per inch for PNG output (default: None)
        sys_inputs: Dictionary of values to pass to template
                   Values should be JSON-serializable strings
                   Example: {"name": "John", "items": json.dumps([...])}
        download: If True, force download; if False, display inline (default: False)

    Returns:
        Compiled output with appropriate content-type header

    Example:
        # JavaScript API call
        frappe.call({
            method: 'frappe_typst.utils.typst.generate',
            args: {
                file: 'FILE-000123',
                format: 'pdf',
                sys_inputs: {name: 'John', total: '1000'}
            }
        })

        # Direct URL
        /api/method/frappe_typst.utils.typst.generate?file=FILE-000123&format=pdf&download=1
    """
    # Parse sys_inputs from JSON string if provided as string
    if isinstance(sys_inputs, str):
        sys_inputs = json.loads(sys_inputs)

    # Build and compile response
    builder = build(doc=file)
    builder.compile_response(
        format=format,
        ppi=ppi,
        sys_inputs=sys_inputs,
        download=bool(download),
    )
