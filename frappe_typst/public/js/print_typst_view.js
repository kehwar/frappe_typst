/**
 * Typst-aware print preview for frappe.ui.form.PrintView.
 *
 * Loaded via page_js on the "print" page — runs after the page bundle defines
 * frappe.ui.form.PrintView so the class extension is safe.
 *
 * For Typst print formats (print_format_type === "Typst"):
 *   - preview(): embeds the compiled PDF in an <object> element instead of
 *     trying to render the Jinja+Typst source as HTML.
 *   - render_pdf(): opens the PDF download URL in a new tab (bypasses the
 *     wkhtmltopdf validity check that is irrelevant for Typst).
 *
 * For all other formats, calls super.*() without modification.
 */

frappe.ui.form.PrintView = class FrappeTypstPrintView extends frappe.ui.form.PrintView {
    make() {
        super.make();

        // Inject a dedicated wrapper for the PDF <object> element.
        // Sits alongside .print-preview-wrapper and .preview-beta-wrapper.
        this.print_wrapper.find(".print-preview-wrapper").after(
            `<div class="typst-preview-wrapper" style="display:none;">
                <div class="typst-pdf-container"></div>
             </div>`
        );
    }

    preview() {
        const print_format = this.get_print_format();

        if (print_format.print_format_type === "Typst") {
            this.print_wrapper.find(".print-preview-wrapper").hide();
            this.print_wrapper.find(".preview-beta-wrapper").hide();
            this.print_wrapper.find(".print-designer-wrapper").hide();
            this.print_wrapper.find(".typst-preview-wrapper").show();
            this._preview_typst_pdf(print_format);
            return;
        }

        this.print_wrapper.find(".typst-preview-wrapper").hide();
        super.preview();
    }

    _preview_typst_pdf(print_format) {
        const container = this.print_wrapper.find(".typst-pdf-container")[0];
        $(container).empty();

        // Build the download_pdf URL — pdf_generator is read from the Print
        // Format document on the server so we don't need to pass it explicitly.
        const params = new URLSearchParams({
            doctype: this.frm.doc.doctype,
            name: this.frm.doc.name,
            format: this.selected_format(),
            no_letterhead: this.with_letterhead() ? "0" : "1",
            letterhead: this.get_letterhead(),
        });
        if (this.lang_code) params.set("_lang", this.lang_code);

        const url = `/api/method/frappe.utils.print_format.download_pdf?${params}`;

        // <object type="application/pdf"> renders inline in modern browsers
        // even when the server sends Content-Disposition: attachment.
        const obj = document.createElement("object");
        obj.type = "application/pdf";
        obj.style.width = "100%";
        obj.style.height = "0";
        obj.data = url;
        container.appendChild(obj);

        obj.addEventListener("load", () => {
            obj.style.height = "calc(100vh - var(--page-head-height) - var(--navbar-height))";
        });
        obj.addEventListener("error", () => {
            frappe.show_alert({ message: __("Error generating PDF preview"), indicator: "red" }, 8);
            this.print_wrapper.find(".typst-preview-wrapper").hide();
            super.preview();
        });
    }

    render_pdf() {
        const print_format = this.get_print_format();

        if (print_format.print_format_type === "Typst") {
            this.render_page("/api/method/frappe.utils.print_format.download_pdf?");
            return;
        }

        super.render_pdf();
    }

    printit() {
        const print_format = this.get_print_format();

        if (print_format.print_format_type === "Typst") {
            // Open the PDF in a new tab — the browser's native PDF viewer
            // provides its own print button, which prints the actual PDF.
            this.render_page("/api/method/frappe.utils.print_format.download_pdf?");
            return;
        }

        super.printit();
    }
};
