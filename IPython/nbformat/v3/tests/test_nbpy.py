# -*- coding: utf8 -*-
from . import formattest

from .. import nbpy
from .nbexamples import nb0, nb0_py


class TestPy(formattest.NBFormatTestCase):

    nb0_ref = nb0_py
    ext = 'py'
    mod = nbpy
    ignored_keys = ['collapsed', 'outputs', 'prompt_number', 'metadata']

    def assertSubset(self, da, db):
        """assert that da is a subset of db, ignoring self.ignored_keys.
        
        Called recursively on containers, ultimately comparing individual
        elements.
        """
        if isinstance(da, dict):
            for k,v in da.iteritems():
                if k in self.ignored_keys:
                    continue
                self.assertTrue(k in db)
                self.assertSubset(v, db[k])
        elif isinstance(da, list):
            for a,b in zip(da, db):
                self.assertSubset(a,b)
        else:
            self.assertEquals(da, db)
        return True
    
    def assertNBEquals(self, nba, nbb):
        # since roundtrip is lossy, only compare keys that are preserved
        # assumes nba is read from my file format
        return self.assertSubset(nba, nbb)
        
