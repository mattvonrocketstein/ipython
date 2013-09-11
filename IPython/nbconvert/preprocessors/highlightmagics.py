"""This preprocessor detect cells using a different language through
magic extensions such as `%%R` or `%%octave`. Cell's metadata is marked
so that the appropriate highlighter can be used in the `highlight`
filter.
"""

#-----------------------------------------------------------------------------
# Copyright (c) 2013, the IPython Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

from __future__ import print_function, absolute_import

import re

# Our own imports
# Needed to override preprocessor
from .base import (Preprocessor)
from IPython.utils.traitlets import Dict

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class HighlightMagicsPreprocessor(Preprocessor):
    """
    Detects and tags code cells that use a different languages than Python.
    """

    # list of magic language extensions and their associated pygment lexers
    languages = Dict(
        default_value={
            '%%R': 'r',
            '%%bash': 'bash',
            '%%octave': 'octave',
            '%%perl': 'perl',
            '%%ruby': 'ruby'},
        config=True,
        help=("Syntax highlighting for magic's extension languages. "
         "Each item associates a language magic extension such as %%R, "
         "with a pygments lexer such as r."))

    def __init__(self, config=None, **kw):
        """Public constructor"""

        super(HighlightMagicsPreprocessor, self).__init__(config=config, **kw)

        # build a regular expression to catch language extensions and choose
        # an adequate pygments lexer
        any_language = "|".join(self.languages.keys())
        self.re_magic_language = re.compile(
            r'^\s*({0})\s+'.format(any_language))

    def which_magic_language(self, source):
        """
        When a cell uses another language through a magic extension,
        the other language is returned.
        If no language magic is detected, this function returns None.

        Parameters
        ----------
        source: str
            Source code of the cell to highlight
        """

        m = self.re_magic_language.match(source)

        if m:
            # By construction of the re, the matched language must be in the
            # languages dictionnary
            assert(m.group(1) in self.languages)
            return self.languages[m.group(1)]
        else:
            return None

    def preprocess_cell(self, cell, resources, cell_index):
        """
        Tags cells using a magic extension language

        Parameters
        ----------
        cell : NotebookNode cell
            Notebook cell being processed
        resources : dictionary
            Additional resources used in the conversion process.  Allows
            preprocessors to pass variables into the Jinja engine.
        cell_index : int
            Index of the cell being processed (see base.py)
        """

        # Only tag code cells
        if hasattr(cell, "input") and cell.cell_type == "code":
            magic_language = self.which_magic_language(cell.input)
            if magic_language:
                cell['metadata']['magics_language'] = magic_language
        return cell, resources
