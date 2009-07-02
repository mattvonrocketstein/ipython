# encoding: utf-8
"""
Test process execution and IO redirection.
"""

__docformat__ = "restructuredtext en"

#-------------------------------------------------------------------------------
#  Copyright (C) 2008  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is
#  in the file COPYING, distributed as part of this software.
#-------------------------------------------------------------------------------

from copy import copy, deepcopy
from cStringIO import StringIO
import string

from nose.tools import assert_equal

from IPython.frontend.prefilterfrontend import PrefilterFrontEnd
from IPython.core.ipapi import get as get_ipython0
from IPython.testing.plugin.ipdoctest import default_argv


def safe_deepcopy(d):
    """ Deep copy every key of the given dict, when possible. Elsewhere
        do a copy.
    """
    copied_d = dict()
    for key, value in d.iteritems():
        try:
            copied_d[key] = deepcopy(value)
        except:
            try:
                copied_d[key] = copy(value)
            except:
                copied_d[key] = value
    return copied_d


class TestPrefilterFrontEnd(PrefilterFrontEnd):
    
    input_prompt_template = string.Template('')
    output_prompt_template = string.Template('')
    banner = ''

    def __init__(self):
        self.out = StringIO()
        PrefilterFrontEnd.__init__(self,argv=default_argv())
        # Some more code for isolation (yeah, crazy)
        self._on_enter()
        self.out.flush()
        self.out.reset()
        self.out.truncate()

    def write(self, string, *args, **kwargs):
       self.out.write(string) 

    def _on_enter(self):
        self.input_buffer += '\n'
        PrefilterFrontEnd._on_enter(self)


def isolate_ipython0(func):
    """ Decorator to isolate execution that involves an iptyhon0.

        Notes
        -----

        Apply only to functions with no arguments. Nose skips functions
        with arguments.
    """
    def my_func():
        iplib = get_ipython0()
        if iplib is None:
            return func()
        ipython0 = iplib.IP
        global_ns = safe_deepcopy(ipython0.user_global_ns)
        user_ns = safe_deepcopy(ipython0.user_ns)
        try:
            out = func()
        finally:
            ipython0.user_ns = user_ns
            ipython0.user_global_ns = global_ns
        # Undo the hack at creation of PrefilterFrontEnd
        from IPython import iplib
        iplib.InteractiveShell.isthreaded = False
        return out

    my_func.__name__ = func.__name__
    return my_func


@isolate_ipython0
def test_execution():
    """ Test execution of a command.
    """
    f = TestPrefilterFrontEnd()
    f.input_buffer = 'print 1'
    f._on_enter()
    out_value = f.out.getvalue()
    assert_equal(out_value, '1\n')


@isolate_ipython0
def test_multiline():
    """ Test execution of a multiline command.
    """
    f = TestPrefilterFrontEnd()
    f.input_buffer = 'if True:'
    f._on_enter()
    f.input_buffer += 'print 1'
    f._on_enter()
    out_value = f.out.getvalue()
    yield assert_equal, out_value, ''
    f._on_enter()
    out_value = f.out.getvalue()
    yield assert_equal, out_value, '1\n'
    f = TestPrefilterFrontEnd()
    f.input_buffer='(1 +'
    f._on_enter()
    f.input_buffer += '0)'
    f._on_enter()
    out_value = f.out.getvalue()
    yield assert_equal, out_value, ''
    f._on_enter()
    out_value = f.out.getvalue()
    yield assert_equal, out_value, '1\n'


@isolate_ipython0
def test_capture():
    """ Test the capture of output in different channels.
    """
    # Test on the OS-level stdout, stderr.
    f = TestPrefilterFrontEnd()
    f.input_buffer = \
            'import os; out=os.fdopen(1, "w"); out.write("1") ; out.flush()'
    f._on_enter()
    out_value = f.out.getvalue()
    yield assert_equal, out_value, '1'
    f = TestPrefilterFrontEnd()
    f.input_buffer = \
            'import os; out=os.fdopen(2, "w"); out.write("1") ; out.flush()'
    f._on_enter()
    out_value = f.out.getvalue()
    yield assert_equal, out_value, '1'

     
@isolate_ipython0
def test_magic():
    """ Test the magic expansion and history.
    
        This test is fairly fragile and will break when magics change.
    """
    f = TestPrefilterFrontEnd()
    # Before checking the interactive namespace, make sure it's clear (it can
    # otherwise pick up things stored in the user's local db)
    f.input_buffer += '%reset -f'
    f._on_enter()
    f.complete_current_input()
    # Now, run the %who magic and check output
    f.input_buffer += '%who'
    f._on_enter()
    out_value = f.out.getvalue()
    assert_equal(out_value, 'Interactive namespace is empty.\n')


@isolate_ipython0
def test_help():
    """ Test object inspection.
    """
    f = TestPrefilterFrontEnd()
    f.input_buffer += "def f():"
    f._on_enter()
    f.input_buffer += "'foobar'"
    f._on_enter()
    f.input_buffer += "pass"
    f._on_enter()
    f._on_enter()
    f.input_buffer += "f?"
    f._on_enter()
    assert 'traceback' not in f.last_result
    ## XXX: ipython doctest magic breaks this. I have no clue why
    #out_value = f.out.getvalue()
    #assert out_value.split()[-1] == 'foobar' 


@isolate_ipython0
def test_completion_simple():
    """ Test command-line completion on trivial examples.
    """
    f = TestPrefilterFrontEnd()
    f.input_buffer = 'zzza = 1'
    f._on_enter()
    f.input_buffer = 'zzzb = 2'
    f._on_enter()
    f.input_buffer = 'zz'
    f.complete_current_input()
    out_value = f.out.getvalue()
    yield assert_equal, out_value, '\nzzza zzzb '
    yield assert_equal, f.input_buffer, 'zzz'


@isolate_ipython0
def test_completion_parenthesis():
    """ Test command-line completion when a parenthesis is open.
    """
    f = TestPrefilterFrontEnd()
    f.input_buffer = 'zzza = 1'
    f._on_enter()
    f.input_buffer = 'zzzb = 2'
    f._on_enter()
    f.input_buffer = 'map(zz'
    f.complete_current_input()
    out_value = f.out.getvalue()
    yield assert_equal, out_value, '\nzzza zzzb '
    yield assert_equal, f.input_buffer, 'map(zzz'


@isolate_ipython0
def test_completion_indexing():
    """ Test command-line completion when indexing on objects.
    """
    f = TestPrefilterFrontEnd()
    f.input_buffer = 'a = [0]'
    f._on_enter()
    f.input_buffer = 'a[0].'
    f.complete_current_input()
    assert_equal(f.input_buffer, 'a[0].__')


@isolate_ipython0
def test_completion_equal():
    """ Test command-line completion when the delimiter is "=", not " ".
    """
    f = TestPrefilterFrontEnd()
    f.input_buffer = 'a=1.'
    f.complete_current_input()
    assert_equal(f.input_buffer, 'a=1.__')



if __name__ == '__main__':
    test_magic()
    test_help()
    test_execution()
    test_multiline()
    test_capture()
    test_completion_simple()
    test_completion_complex()
