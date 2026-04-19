# frappe_typst

[Typst](https://typst.app/) integration for Frappe. Provides PDF generation from Typst markup via Print Formats.

## Features

- **Print Format integration** — use Typst markup as an alternative to Jinja/HTML in Print Formats.
- **PDF generation hook** — `pdf_generator = "typst"` produces PDF bytes via the `typst-py` compiler.
- **Python API** — `TypstBuilder` for programmatic document compilation; `build()` factory and `generate()` whitelisted endpoint.
- **Context injection** — `doc.json`, `user.json`, and `letterhead.json` are available inside every Typst template.
- **Filesystem templates** — `.typ` files and `.tar.gz` archives co-located with a DocType module take priority over the inline `html` field.

## Requirements

- `kehwar/frappe` (custom Frappe fork)
- `typst-py` (`pip install typst`)
- `pypdf` (`pip install pypdf`)

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO
bench install-app frappe_typst
```

## Usage

### In Python

```python
from frappe_typst import TypstBuilder, build, generate

# Compile a Typst string to PDF bytes
pdf_bytes = build("#set page(width: 100pt)\nHello").compile()

# Or use the full builder API
builder = TypstBuilder()
builder.read_string("#strong[Invoice]")
pdf_bytes = builder.compile()
```

### In a Print Format

1. Set **Print Format Type** to `Typst`.
2. Write Typst markup in the **Typst Markup** code field.
3. Set **PDF Generator** to `typst` (auto-set when switching type).
4. Use `doc.json`, `user.json`, `letterhead.json` inside your template:

```typst
#let doc = json("doc.json")
#doc.at("name", default: "")
```

## Contributing

```bash
cd apps/frappe_typst
pre-commit install
```

Tools: `ruff`, `eslint`, `prettier`, `pyupgrade`.

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
