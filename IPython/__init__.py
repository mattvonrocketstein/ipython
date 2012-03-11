# encoding: utf-8
"""
IPython: tools for interactive and parallel computing in Python.

http://ipython.org
"""
#-----------------------------------------------------------------------------
#  Copyright (c) 2008-2011, IPython Development Team.
#  Copyright (c) 2001-2007, Fernando Perez <fernando.perez@colorado.edu>
#  Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
#  Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>
#
#  Distributed under the terms of the Modified BSD License.
#
#  The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
from __future__ import absolute_import

import os
import sys

#-----------------------------------------------------------------------------
# Setup everything
#-----------------------------------------------------------------------------

# Don't forget to also update setup.py when this changes!
if sys.version[0:3] < '2.6':
    raise ImportError('Python Version 2.6 or above is required for IPython.')

# Make it easy to import extensions - they are always directly on pythonpath.
# Therefore, non-IPython modules can be added to extensions directory.
# This should probably be in ipapp.py.
sys.path.append(os.path.join(os.path.dirname(__file__), "extensions"))

#-----------------------------------------------------------------------------
# Setup the top level names
#-----------------------------------------------------------------------------

from .config.loader import Config
from .core import release
from .core.application import Application
from .frontend.terminal.embed import embed

from .core.error import TryNext
from .core.interactiveshell import InteractiveShell
from .testing import test
from .utils.sysinfo import sys_info

# Release data
__author__ = ''
for author, email in release.authors.itervalues():
    __author__ += author + ' <' + email + '>\n'
__license__  = release.license
__version__  = release.version

def caller_module_and_locals():
    """Returns (module, locals) of the caller"""
    caller = sys._getframe(2)
    global_ns = caller.f_globals
    module = sys.modules[global_ns['__name__']]
    return (module, caller.f_locals)

def embed_kernel(module=None, local_ns=None):
    """Call this to embed an IPython kernel at the current point in your program. """
    (caller_module, caller_locals) = caller_module_and_locals()
    if module is None:
        module = caller_module
    if local_ns is None:
        local_ns = caller_locals
    # Only import .zmq when we really need it
    from .zmq.ipkernel import embed_kernel as real_embed_kernel
    real_embed_kernel(module, local_ns)
