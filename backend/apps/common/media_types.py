"""Media types the pipeline recognises by name."""

GENERIC = "application/octet-stream"
PDF = "application/pdf"
WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EXCEL_LEGACY = "application/vnd.ms-excel"

# Types that are text under another name. Anything under text/ is read as
# text without being listed; these are the ones registered elsewhere.
TEXT_LIKE = frozenset(
    {
        "application/json",
        "application/xml",
        "application/sql",
        "application/x-sql",
        "application/yaml",
        "application/x-yaml",
        "application/toml",
        "application/javascript",
        "application/x-sh",
        "application/x-httpd-php",
    }
)

# What a file's suffix says it is, for the cases the interpreter's table gets
# wrong or leaves out. The table is populated from an operating system file
# that slim images do not ship, so it answers nothing for .sql or .xlsx, and a
# browser uploading either usually declares the generic binary type.
BY_SUFFIX = {
    ".docx": WORD,
    ".xlsx": EXCEL,
    ".xlsm": EXCEL,
    ".xls": EXCEL_LEGACY,
    ".pdf": PDF,
    ".sql": "application/sql",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".toml": "application/toml",
    ".json": "application/json",
    ".xml": "application/xml",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".txt": "text/plain",
    ".log": "text/plain",
    ".ini": "text/plain",
    ".cfg": "text/plain",
    ".env": "text/plain",
    ".py": "text/x-python",
    ".js": "application/javascript",
    ".ts": "text/plain",
    ".sh": "application/x-sh",
    ".html": "text/html",
    ".htm": "text/html",
    ".rst": "text/plain",
}
