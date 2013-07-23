# encoding: utf-8
"""
IO capturing utilities.
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2013  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------
from __future__ import print_function

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import sys
from StringIO import StringIO

#-----------------------------------------------------------------------------
# Classes and functions
#-----------------------------------------------------------------------------


class RichOutput(object):
    def __init__(self, source, data, metadata):
        self.source = source
        self.data = data or {}
        self.metadata = metadata or {}
    
    def display(self):
        from IPython.display import publish_display_data
        publish_display_data(self.source, self.data, self.metadata)
    
    def _repr_mime_(self, mime):
        if mime not in self.data:
            return
        data = self.data[mime]
        if mime in self.metadata:
            return data, self.metadata[mime]
        else:
            return data
            
    def _repr_html_(self):
        return self._repr_mime_("text/html")
    
    def _repr_latex_(self):
        return self._repr_mime_("text/latex")
    
    def _repr_json_(self):
        return self._repr_mime_("application/json")
    
    def _repr_javascript_(self):
        return self._repr_mime_("application/javascript")
    
    def _repr_png_(self):
        return self._repr_mime_("image/png")
    
    def _repr_jpeg_(self):
        return self._repr_mime_("image/jpg")
    
    def _repr_svg_(self):
        return self._repr_mime_("image/svg+xml")


class CapturedIO(object):
    """Simple object for containing captured stdout/err StringIO objects"""
    
    def __init__(self, stdout, stderr, outputs=None):
        self._stdout = stdout
        self._stderr = stderr
        if outputs is None:
            outputs = []
        self._outputs = outputs
    
    def __str__(self):
        return self.stdout
    
    @property
    def stdout(self):
        if not self._stdout:
            return ''
        return self._stdout.getvalue()
    
    @property
    def stderr(self):
        if not self._stderr:
            return ''
        return self._stderr.getvalue()
    
    def show(self):
        """write my output to sys.stdout/err as appropriate"""
        sys.stdout.write(self.stdout)
        sys.stderr.write(self.stderr)
        sys.stdout.flush()
        sys.stderr.flush()
        for source, data, metadata in self._outputs:
            RichOutput(source, data, metadata).display()
    
    __call__ = show


class capture_output(object):
    """context manager for capturing stdout/err"""
    stdout = True
    stderr = True
    display = True
    
    def __init__(self, stdout=True, stderr=True, display=True):
        self.stdout = stdout
        self.stderr = stderr
        self.display = display
        self.shell = None
    
    def __enter__(self):
        from IPython.core.getipython import get_ipython
        from IPython.core.displaypub import CapturingDisplayPublisher
        
        self.sys_stdout = sys.stdout
        self.sys_stderr = sys.stderr
        
        if self.display:
            self.shell = get_ipython()
            if self.shell is None:
                self.save_display_pub = None
                self.display = False
        
        stdout = stderr = outputs = False
        if self.stdout:
            stdout = sys.stdout = StringIO()
        if self.stderr:
            stderr = sys.stderr = StringIO()
        if self.display:
            self.save_display_pub = self.shell.display_pub
            self.shell.display_pub = CapturingDisplayPublisher()
            outputs = self.shell.display_pub.outputs
            
        
        return CapturedIO(stdout, stderr, outputs)
    
    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr
        if self.display and self.shell:
            self.shell.display_pub = self.save_display_pub


