# ruff: noqa: D100
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import sys
import os

project = 'smolarith'
copyright = '2024, William D. Jones'
author = 'William D. Jones'
release = '0.1.0'

sys.path.append(os.path.abspath('../src'))

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["myst_parser",
              "sphinx.ext.autodoc",
              "sphinx.ext.intersphinx",
              "sphinx_rtd_theme",
              "sphinx.ext.doctest",
              "sphinx.ext.napoleon",
              "sphinx.ext.todo",
              "sphinx.ext.mathjax"]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

intersphinx_mapping = {'python': ('https://docs.python.org/3', None),
                       'amaranth': ('https://amaranth-lang.org/docs/amaranth/v0.4.2/', None)}  # noqa: E501
autodoc_default_options = {"members": True,
                           "undoc-members": True}
todo_include_todos = True
napoleon_custom_sections = ["Future Directions"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']
