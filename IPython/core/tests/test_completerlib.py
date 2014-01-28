# -*- coding: utf-8 -*-
"""Tests for completerlib.

"""
from __future__ import absolute_import

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import os
import shutil
import sys
import tempfile
import unittest
from os.path import join

import nose.tools as nt

from IPython.core.completerlib import magic_run_completer, module_completion
from IPython.utils import py3compat
from IPython.utils.tempdir import TemporaryDirectory
from IPython.testing.decorators import onlyif_unicode_paths


class MockEvent(object):
    def __init__(self, line):
        self.line = line

#-----------------------------------------------------------------------------
# Test functions begin
#-----------------------------------------------------------------------------
class Test_magic_run_completer(unittest.TestCase):
    files = [u"aao.py", u"a.py", u"b.py", u"aao.txt"]
    dirs = [u"adir/", "bdir/"]

    def setUp(self):
        self.BASETESTDIR = tempfile.mkdtemp()
        for fil in self.files:
            with open(join(self.BASETESTDIR, fil), "w") as sfile:
                sfile.write("pass\n")
        for d in self.dirs:
            os.mkdir(join(self.BASETESTDIR, d))

        self.oldpath = py3compat.getcwd()
        os.chdir(self.BASETESTDIR)

    def tearDown(self):
        os.chdir(self.oldpath)
        shutil.rmtree(self.BASETESTDIR)

    def test_1(self):
        """Test magic_run_completer, should match two alterntives
        """
        event = MockEvent(u"%run a")
        mockself = None
        match = set(magic_run_completer(mockself, event))
        self.assertEqual(match, {u"a.py", u"aao.py", u"adir/"})

    def test_2(self):
        """Test magic_run_completer, should match one alterntive
        """
        event = MockEvent(u"%run aa")
        mockself = None
        match = set(magic_run_completer(mockself, event))
        self.assertEqual(match, set([u"aao.py"]))

    def test_3(self):
        """Test magic_run_completer with unterminated " """
        event = MockEvent(u'%run "a')
        mockself = None
        match = set(magic_run_completer(mockself, event))
        self.assertEqual(match, {u"a.py", u"aao.py", u"adir/"})

    def test_completion_more_args(self):
        event = MockEvent(u'%run a.py ')
        match = set(magic_run_completer(None, event))
        self.assertEqual(match, set(self.files + self.dirs))

    def test_completion_in_dir(self):
        # Github issue #3459
        event = MockEvent(u'%run a.py {}'.format(join(self.BASETESTDIR, 'a')))
        print(repr(event.line))
        match = set(magic_run_completer(None, event))
        self.assertEqual(match, {join(self.BASETESTDIR, f) for
                                f in (u'a.py', u'aao.py', u'aao.txt', u'adir/')})

class Test_magic_run_completer_nonascii(unittest.TestCase):
    @onlyif_unicode_paths
    def setUp(self):
        self.BASETESTDIR = tempfile.mkdtemp()
        for fil in [u"aaø.py", u"a.py", u"b.py"]:
            with open(join(self.BASETESTDIR, fil), "w") as sfile:
                sfile.write("pass\n")
        self.oldpath = py3compat.getcwd()
        os.chdir(self.BASETESTDIR)

    def tearDown(self):
        os.chdir(self.oldpath)
        shutil.rmtree(self.BASETESTDIR)

    @onlyif_unicode_paths
    def test_1(self):
        """Test magic_run_completer, should match two alterntives
        """
        event = MockEvent(u"%run a")
        mockself = None
        match = set(magic_run_completer(mockself, event))
        self.assertEqual(match, set([u"a.py", u"aaø.py"]))

    @onlyif_unicode_paths
    def test_2(self):
        """Test magic_run_completer, should match one alterntive
        """
        event = MockEvent(u"%run aa")
        mockself = None
        match = set(magic_run_completer(mockself, event))
        self.assertEqual(match, set([u"aaø.py"]))

    @onlyif_unicode_paths
    def test_3(self):
        """Test magic_run_completer with unterminated " """
        event = MockEvent(u'%run "a')
        mockself = None
        match = set(magic_run_completer(mockself, event))
        self.assertEqual(match, set([u"a.py", u"aaø.py"]))

# module_completer:

def test_import_invalid_module():
    """Testing of issue https://github.com/ipython/ipython/issues/1107"""
    invalid_module_names = set(['foo-bar', 'foo:bar', '10foo'])
    valid_module_names = set(['foobar'])
    with TemporaryDirectory() as tmpdir:
        sys.path.insert( 0, tmpdir )
        for name in invalid_module_names | valid_module_names:
            filename = os.path.join(tmpdir, name + '.py')
            open(filename, 'w').close()

        s = set( module_completion('import foo') )
        intersection = s.intersection(invalid_module_names)
        nt.assert_equal(intersection, set())

        assert valid_module_names.issubset(s), valid_module_names.intersection(s)
