/**
 * Print Format form controller — Typst type UX enhancements.
 *
 * When print_format_type is "Typst":
 *  - Relabels the html Code field to "Typst Markup" and sets its syntax to Typst.
 *  - Auto-sets pdf_generator to "typst".
 *
 * When switching away from "Typst":
 *  - Restores the html field label back to "HTML".
 */

frappe.ui.form.on('Print Format', {
    refresh(frm) {
        _apply_typst_field_labels(frm)
    },

    print_format_type(frm) {
        _apply_typst_field_labels(frm)

        if (frm.doc.print_format_type === 'Typst') {
            frm.set_value('pdf_generator', 'typst')
        }
    },
})

function _apply_typst_field_labels(frm) {
    const is_typst = frm.doc.print_format_type === 'Typst'
    frm.set_df_property('html', 'label', is_typst ? __('Typst Markup') : __('HTML'))
    frm.set_df_property('html', 'options', is_typst ? 'Typst' : 'Jinja')
    frm.refresh_field('html')
}
