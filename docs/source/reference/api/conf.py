import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE_ROOT.parents[1]))

project = "CyteBase API"
copyright = "2026, Parashar Dhapola"
author = "Parashar Dhapola"
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "sphinx.ext.mathjax",
    "sphinx_copybutton",
]
autosummary_generate = False
master_doc = "index"
exclude_patterns = ["_build", "**.ipynb_checkpoints"]
myst_enable_extensions = ["colon_fence"]
myst_all_links_external = True
pygments_style = "sphinx"
language = "en"

html_theme = "sphinx_book_theme"
templates_path = ["_templates"]
html_sidebars = {"**": ["docs-navigation.html"]}
html_css_files = ["https://docs.nygen.io/assets/brand/docs.css"]
html_logo = "https://docs.nygen.io/assets/brand/logo/cytebase.svg"
html_favicon = "https://docs.nygen.io/assets/brand/logo/cytebase.ico"
html_title = "CyteBase API reference"
html_baseurl = "https://docs.nygen.io/CyteBase/api/"
html_theme_options = {
    "logo": {"text": "CyteBase", "alt_text": "CyteBase"},
    "repository_url": "https://github.com/NygenAnalytics/CyteBase",
    "path_to_docs": "docs/source/reference/api",
    "article_header_start": [],
    "article_header_end": ["toggle-secondary-sidebar.html"],
    "show_prev_next": False,
    "footer_content_items": ["extra-footer.html"],
    "extra_footer": '<a class="docs-home-link" href="https://docs.nygen.io/"><img class="brand-symbol" src="https://docs.nygen.io/assets/brand/logo/nygen-symbol.svg" alt="Nygen documentation home" width="32" height="32"></a>',
    "show_navbar_depth": 2,
    "navigation_with_keys": False,
}

nitpick_ignore = [
    ("py:class", "_duckdb.DuckDBPyConnection"),
    ("py:class", "pandas.DataFrame"),
    ("py:data", "Ellipsis"),
]
# CyteArc documents its own types, such as DataStore and ArtifactRef, in its
# reference; this one names them without links.
nitpick_ignore_regex = [
    ("py:class", r"cytearc\..*"),
    ("py:obj", r"cytearc\..*"),
]
