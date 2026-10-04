# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import os
import sys
sys.path.insert(0, os.path.abspath('../../src'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'brilliant_msg'
copyright = '2025, luke-brilliant'
author = 'luke-brilliant'
# Derived from the installed package metadata so it cannot drift from
# pyproject.toml the way a hardcoded string does.
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    release = _pkg_version("brilliant-msg")
except PackageNotFoundError:  # building without an install
    release = "0.0.0.dev0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_rtd_theme',
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}
autodoc_member_order = 'bysource' # Show members in the order they appear in the source code
