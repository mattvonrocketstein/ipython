# encoding: utf-8
"""
Object for encapsulating process execution by using callbacks for stdout, 
stderr and stdin.
"""
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
from subprocess import Popen, PIPE
from threading import Thread


class PipedProcess(Thread):

    def __init__(self, command_string, out_callback, 
                        end_callback=None,):
        self.command_string = command_string
        self.out_callback = out_callback
        self.end_callback = end_callback
        Thread.__init__(self)
    

    def run(self):
        """ Start the process and hook up the callbacks.
        """
        process = Popen((self.command_string + ' 2>&1', ), shell=True,
                                universal_newlines=True,
                                stdout=PIPE, stdin=PIPE)
        self.process = process
        while True:
            out_char = process.stdout.read(1)
            if out_char == '' and process.poll() is not None:
                break
            self.out_callback(out_char)

        if self.end_callback is not None:
            self.end_callback()
    

