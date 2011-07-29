"""The basic dict based notebook format."""

import pprint
import uuid

from IPython.utils.ipstruct import Struct


class NotebookNode(Struct):
    pass


def from_dict(d):
    if isinstance(d, dict):
        newd = NotebookNode()
        for k,v in d.items():
            newd[k] = from_dict(v)
        return newd
    elif isinstance(d, (tuple, list)):
        return [from_dict(i) for i in d]
    else:
        return d


def new_code_cell(code=None, prompt_number=None):
    """Create a new code cell with input and output"""
    cell = NotebookNode()
    cell.cell_type = u'code'
    if code is not None:
        cell.code = unicode(code)
    if prompt_number is not None:
        cell.prompt_number = int(prompt_number)
    return cell


def new_text_cell(text=None):
    """Create a new text cell."""
    cell = NotebookNode()
    if text is not None:
        cell.text = unicode(text)
    cell.cell_type = u'text'
    return cell


def new_notebook(cells=None):
    """Create a notebook by name, id and a list of worksheets."""
    nb = NotebookNode()
    if cells is not None:
        nb.cells = cells
    else:
        nb.cells = []
    return nb

