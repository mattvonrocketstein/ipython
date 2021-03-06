# -*- coding: utf-8 -*-
"""Tests for shellapp module.

Authors
-------
* Bradley Froehle
"""
#-----------------------------------------------------------------------------
#  Copyright (C) 2012  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
import unittest

from IPython.testing import decorators as dec
from IPython.testing import tools as tt
from IPython.utils.py3compat import PY3

sqlite_err_maybe = dec.module_not_available('sqlite3')
SQLITE_NOT_AVAILABLE_ERROR = ('WARNING: IPython History requires SQLite,'
                              ' your history will not be saved\n')

class TestFileToRun(unittest.TestCase, tt.TempFileMixin):
    """Test the behavior of the file_to_run parameter."""

    def test_py_script_file_attribute(self):
        """Test that `__file__` is set when running `ipython file.py`"""
        src = "print(__file__)\n"
        self.mktmp(src)

        err = SQLITE_NOT_AVAILABLE_ERROR if sqlite_err_maybe else None
        tt.ipexec_validate(self.fname, self.fname, err)

    def test_ipy_script_file_attribute(self):
        """Test that `__file__` is set when running `ipython file.ipy`"""
        src = "print(__file__)\n"
        self.mktmp(src, ext='.ipy')

        err = SQLITE_NOT_AVAILABLE_ERROR if sqlite_err_maybe else None
        tt.ipexec_validate(self.fname, self.fname, err)

    def test_py_script_file_attribute_interactively(self):
        """Test that `__file__` is not set after `ipython -i file.py`"""
        src = "True\n"
        self.mktmp(src)

        err = SQLITE_NOT_AVAILABLE_ERROR if sqlite_err_maybe else None
        tt.ipexec_validate(self.fname, 'False', err, options=['-i'],
                           commands=['"__file__" in globals()', 'exit()'])

    @dec.skipif(PY3)
    def test_py_script_file_compiler_directive(self):
        """Test `__future__` compiler directives with `ipython -i file.py`"""
        src = "from __future__ import division\n"
        self.mktmp(src)

        err = SQLITE_NOT_AVAILABLE_ERROR if sqlite_err_maybe else None
        tt.ipexec_validate(self.fname, 'float', err, options=['-i'],
                           commands=['type(1/2)', 'exit()'])
