"""Generic testing tools that do NOT depend on Twisted.

In particular, this module exposes a set of top-level assert* functions that
can be used in place of nose.tools.assert* in method generators (the ones in
nose can not, at least as of nose 0.10.4).

Note: our testing package contains testing.util, which does depend on Twisted
and provides utilities for tests that manage Deferreds.  All testing support
tools that only depend on nose, IPython or the standard library should go here
instead.


Authors
-------
- Fernando Perez <Fernando.Perez@berkeley.edu>
"""

#*****************************************************************************
#       Copyright (C) 2009 The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#*****************************************************************************

#-----------------------------------------------------------------------------
# Required modules and packages
#-----------------------------------------------------------------------------

import os
import re
import sys
import tempfile

import nose.tools as nt

from IPython.utils import genutils, platutils

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------

# Make a bunch of nose.tools assert wrappers that can be used in test
# generators.  This will expose an assert* function for each one in nose.tools.

_tpl = """
def %(name)s(*a,**kw):
    return nt.%(name)s(*a,**kw)
"""

for _x in [a for a in dir(nt) if a.startswith('assert')]:
    exec _tpl % dict(name=_x)

#-----------------------------------------------------------------------------
# Functions and classes
#-----------------------------------------------------------------------------


def full_path(startPath,files):
    """Make full paths for all the listed files, based on startPath.

    Only the base part of startPath is kept, since this routine is typically
    used with a script's __file__ variable as startPath.  The base of startPath
    is then prepended to all the listed files, forming the output list.

    Parameters
    ----------
      startPath : string
        Initial path to use as the base for the results.  This path is split
      using os.path.split() and only its first component is kept.

      files : string or list
        One or more files.

    Examples
    --------

    >>> full_path('/foo/bar.py',['a.txt','b.txt'])
    ['/foo/a.txt', '/foo/b.txt']

    >>> full_path('/foo',['a.txt','b.txt'])
    ['/a.txt', '/b.txt']

    If a single file is given, the output is still a list:
    >>> full_path('/foo','a.txt')
    ['/a.txt']
    """

    files = genutils.list_strings(files)
    base = os.path.split(startPath)[0]
    return [ os.path.join(base,f) for f in files ]


def parse_test_output(txt):
    """Parse the output of a test run and return errors, failures.

    Parameters
    ----------
    txt : str
      Text output of a test run, assumed to contain a line of one of the
      following forms::
        'FAILED (errors=1)'
        'FAILED (failures=1)'
        'FAILED (errors=1, failures=1)'

    Returns
    -------
    nerr, nfail: number of errors and failures.
    """

    err_m = re.search(r'^FAILED \(errors=(\d+)\)', txt, re.MULTILINE)
    if err_m:
        nerr = int(err_m.group(1))
        nfail = 0
        return  nerr, nfail
    
    fail_m = re.search(r'^FAILED \(failures=(\d+)\)', txt, re.MULTILINE)
    if fail_m:
        nerr = 0
        nfail = int(fail_m.group(1))
        return  nerr, nfail

    both_m = re.search(r'^FAILED \(errors=(\d+), failures=(\d+)\)', txt,
                       re.MULTILINE)
    if both_m:
        nerr = int(both_m.group(1))
        nfail = int(both_m.group(2))
        return  nerr, nfail
    
    # If the input didn't match any of these forms, assume no error/failures
    return 0, 0


# So nose doesn't think this is a test
parse_test_output.__test__ = False


def temp_pyfile(src, ext='.py'):
    """Make a temporary python file, return filename and filehandle.

    Parameters
    ----------
    src : string or list of strings (no need for ending newlines if list)
      Source code to be written to the file.

    ext : optional, string
      Extension for the generated file.

    Returns
    -------
    (filename, open filehandle)
      It is the caller's responsibility to close the open file and unlink it.
    """
    fname = tempfile.mkstemp(ext)[1]
    f = open(fname,'w')
    f.write(src)
    f.flush()
    return fname, f


def default_argv():
    """Return a valid default argv for creating testing instances of ipython"""

    # Get the install directory for the user configuration and tell ipython to
    # use the default profile from there.
    from IPython.config import default
    ipcdir = os.path.dirname(default.__file__)
    ipconf = os.path.join(ipcdir,'ipython_config.py')
    #print 'conf:',ipconf # dbg
    return ['--colors=NoColor', '--no-term-title','--no-banner',
            '--config-file=%s' % ipconf, '--autocall=0', '--quick']
    

def ipexec(fname):
    """Utility to call 'ipython filename'.

    Starts IPython witha minimal and safe configuration to make startup as fast
    as possible.

    Note that this starts IPython in a subprocess!

    Parameters
    ----------
    fname : str
      Name of file to be executed (should have .py or .ipy extension).

    Returns
    -------
    (stdout, stderr) of ipython subprocess.
    """  
    _ip = get_ipython()
    test_dir = os.path.dirname(__file__)
    full_fname = os.path.join(test_dir, fname)
    ipython_cmd = platutils.find_cmd('ipython')
    cmdargs = ' '.join(default_argv())
    return genutils.getoutputerror('%s %s' % (ipython_cmd, full_fname))


def ipexec_validate(fname, expected_out, expected_err=None):
    """Utility to call 'ipython filename' and validate output/error.

    This function raises an AssertionError if the validation fails.

    Note that this starts IPython in a subprocess!

    Parameters
    ----------
    fname : str
      Name of the file to be executed (should have .py or .ipy extension).

    expected_out : str
      Expected stdout of the process.

    Returns
    -------
    None
    """

    out, err = ipexec(fname)
    nt.assert_equals(out.strip(), expected_out.strip())
    if expected_err:
        nt.assert_equals(err.strip(), expected_err.strip())
