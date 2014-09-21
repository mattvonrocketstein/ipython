# -*- coding: utf-8 -*-
"""
The cython magic has been integrated into Cython itself, 
which is now released in version 0.21.

cf github `cython` organisation, `cython` repo, under the 
file `Cython/Build/IpythonMagic.py`
"""
#-----------------------------------------------------------------------------
# Copyright (C) 2010-2011, IPython Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

from __future__ import print_function

try:
    import Cython
except:
    Cython = None

try:
    from Cython.Build.IpythonMagic import CythonMagics
except :
    pass


## still load the magic in IPython 3.x, remove completely in future versions.
def load_ipython_extension(ip):
    """Load the extension in IPython."""
    
    print("""The Cython magic has been move to the Cython package, hence """)
    print("""`%load_ext cythonmagic` is deprecated; Please use `%load_ext cython` instead.""")
    
    if Cython is None or tuple(map(int,Cython.__version__.split('.'))) < (0,21) : 
        print("You need Cython version >=0.21 to use the Cython magic")
        return 
    print("""\nThough, because I am nice, I'll still try to load it for you this time.""")
    Cython.load_ipython_extension(ip)
