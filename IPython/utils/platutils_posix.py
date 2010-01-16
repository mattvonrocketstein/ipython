# -*- coding: utf-8 -*-
""" Platform specific utility functions, posix version 

Importing this module directly is not portable - rather, import platutils 
to use these functions in platform agnostic fashion.
"""

#*****************************************************************************
#       Copyright (C) 2001-2006 Fernando Perez <fperez@colorado.edu>
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#*****************************************************************************
#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
from __future__ import absolute_import

import sys
import os

from .baseutils import getoutputerror

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------

ignore_termtitle = True

#-----------------------------------------------------------------------------
# Functions
#-----------------------------------------------------------------------------

def _dummy_op(*a, **b):
    """ A no-op function """


def _set_term_title_xterm(title):
    """ Change virtual terminal title in xterm-workalikes """
    sys.stdout.write('\033]0;%s\007' % title)

TERM = os.environ.get('TERM','')

if (TERM == 'xterm') or (TERM == 'xterm-color'):
    set_term_title = _set_term_title_xterm
else:
    set_term_title = _dummy_op


def find_cmd(cmd):
    """Find the full path to a command using which."""
    return getoutputerror('/usr/bin/env which %s' % cmd)[0]


def get_long_path_name(path):
    """Dummy no-op."""
    return path


def term_clear():
    os.system('clear')
