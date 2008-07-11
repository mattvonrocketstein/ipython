# encoding: utf-8

"""A parallelized function that does scatter/execute/gather."""

__docformat__ = "restructuredtext en"

#-------------------------------------------------------------------------------
#  Copyright (C) 2008  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Imports
#-------------------------------------------------------------------------------

from types import FunctionType
from zope.interface import Interface, implements


class ParallelFunction(object):
    """
    A decorator for building parallel functions.
    """
    
    def __init__(self, multiengine, dist='b', targets='all', block=True):
        """
        Create a `ParallelFunction decorator`.
        """
        self.multiengine = multiengine
        self.dist = dist
        self.targets = targets
        self.block = block
        
    def __call__(self, func):
        """
        Decorate the function to make it run in parallel.
        """
        assert isinstance(func, (str, FunctionType)), "func must be a fuction or str"
        self.func = func
        def call_function(*sequences):
            return self.multiengine._map(self.func, sequences, dist=self.dist,
                targets=self.targets, block=self.block)
        return call_function

    