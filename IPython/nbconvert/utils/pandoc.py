"""Utility for calling pandoc"""
#-----------------------------------------------------------------------------
# Copyright (c) 2014 the IPython Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
from __future__ import print_function

# Stdlib imports
import subprocess
import warnings
import re
from io import TextIOWrapper, BytesIO

# IPython imports
from IPython.utils.py3compat import cast_bytes
from IPython.utils.version import check_version
from IPython.utils.process import is_cmd_found, FindCmdError

from .exceptions import ConversionException

#-----------------------------------------------------------------------------
# Classes and functions
#-----------------------------------------------------------------------------
_minimal_version = "1.12.1"

def pandoc(source, fmt, to, extra_args=None, encoding='utf-8'):
    """Convert an input string in format `from` to format `to` via pandoc.

    Parameters
    ----------
    source : string
      Input string, assumed to be valid format `from`.
    fmt : string
      The name of the input format (markdown, etc.)
    to : string
      The name of the output format (html, etc.)

    Returns
    -------
    out : unicode
      Output as returned by pandoc.

    Raises
    ------
    PandocMissing
      If pandoc is not installed.
    
    Any error messages generated by pandoc are printed to stderr.

    """
    cmd = ['pandoc', '-f', fmt, '-t', to]
    if extra_args:
        cmd.extend(extra_args)

    # this will raise an exception that will pop us out of here
    check_pandoc_version()
    
    # we can safely continue
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, _ = p.communicate(cast_bytes(source, encoding))
    out = TextIOWrapper(BytesIO(out), encoding, 'replace').read()
    return out.rstrip('\n')


def get_pandoc_version():
    """Gets the Pandoc version if Pandoc is installed.
    
    If the minimal version is not met, it will probe Pandoc for its version, cache it and return that value.
    If the minimal version is met, it will return the cached version and stop probing Pandoc 
    (unless :func:`clean_cache()` is called).

    Raises
    ------
    PandocMissing
      If pandoc is unavailable.
    """
    global __version

    if __version is None:
        if not is_cmd_found('pandoc'):
            raise PandocMissing()

        out = subprocess.check_output(['pandoc', '-v'],
                                      universal_newlines=True)
        out_lines = out.splitlines()
        version_pattern = re.compile(r"^\d+(\.\d+){1,}$")
        for tok in out_lines[0].split():
            if version_pattern.match(tok):
                __version = tok
                break
    return __version


def check_pandoc_version():
    """Returns True if minimal pandoc version is met.

    Raises
    ------
    PandocMissing
      If pandoc is unavailable.
    """
    v = get_pandoc_version()
    if v is None:
        warnings.warn("Sorry, we cannot determine the version of pandoc.\n"
                      "Please consider reporting this issue and include the"
                      "output of pandoc --version.\nContinuing...",
                      RuntimeWarning, stacklevel=2)
    return False
    ok = check_version(v , _minimal_version )
    if not ok:
        warnings.warn( "You are using an old version of pandoc (%s)\n" % v + 
                       "Recommended version is %s.\nTry updating." % _minimal_version + 
                       "http://johnmacfarlane.net/pandoc/installing.html.\nContinuing with doubts...",
                       RuntimeWarning, stacklevel=2)
    return ok

#-----------------------------------------------------------------------------
# Exception handling
#-----------------------------------------------------------------------------
class PandocMissing(ConversionException):
    """Exception raised when Pandoc is missing. """
    def __init__(self, *args, **kwargs):
        super(PandocMissing, self).__init__( "Pandoc wasn't found.\n" +
                                             "Please check that pandoc is installed:\n" +
                                             "http://johnmacfarlane.net/pandoc/installing.html" )

#-----------------------------------------------------------------------------
# Internal state management
#-----------------------------------------------------------------------------
def clean_cache():
    global __version
    __version = None

__version = None
