# -*- coding: utf-8 -*-
"""
Qt4's inputhook support function

Author: Christian Boos
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2011  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

from IPython.external.qt_for_kernel import QtCore, QtGui
from IPython.lib.inputhook import allow_CTRL_C, ignore_CTRL_C, stdin_ready

#-----------------------------------------------------------------------------
# Code
#-----------------------------------------------------------------------------

def create_inputhook_qt4(mgr, app=None):
    """Create an input hook for running the Qt4 application event loop.

    Parameters
    ----------
    mgr : an InputHookManager

    app : Qt Application, optional.
        Running application to use.  If not given, we probe Qt for an
        existing application object, and create a new one if none is found.

    Returns
    -------
    A pair consisting of a Qt Application (either the one given or the
    one found or created) and a inputhook.

    Notes
    -----
    We use a custom input hook instead of PyQt4's default one, as it
    interacts better with the readline packages (issue #481).

    The inputhook function works in tandem with a 'pre_prompt_hook'
    which automatically restores the hook as an inputhook in case the
    latter has been temporarily disabled after having intercepted a
    KeyboardInterrupt.
    """

    if app is None:
        app = QtCore.QCoreApplication.instance()
        if app is None:
            app = QtGui.QApplication([" "])

    # Re-use previously created inputhook if any
    ip = get_ipython()
    if hasattr(ip, '_inputhook_qt4'):
        return app, ip._inputhook_qt4

    # Otherwise create the inputhook_qt4/preprompthook_qt4 pair of
    # hooks (they both share the got_kbdint flag)

    got_kbdint = [False]

    def inputhook_qt4():
        """PyOS_InputHook python hook for Qt4.

        Process pending Qt events and if there's no pending keyboard
        input, spend a short slice of time (50ms) running the Qt event
        loop.

        As a Python ctypes callback can't raise an exception, we catch
        the KeyboardInterrupt and temporarily deactivate the hook,
        which will let a *second* CTRL+C be processed normally and go
        back to a clean prompt line.
        """
        try:
            allow_CTRL_C()
            app = QtCore.QCoreApplication.instance()
            app.processEvents(QtCore.QEventLoop.AllEvents, 300)
            if not stdin_ready():
                timer = QtCore.QTimer()
                timer.timeout.connect(app.quit)
                while not stdin_ready():
                    timer.start(50)
                    app.exec_()
                    timer.stop()
            ignore_CTRL_C()
        except KeyboardInterrupt:
            ignore_CTRL_C()
            got_kbdint[0] = True
            print("\nKeyboardInterrupt - qt4 event loop interrupted!"
                  "\n  * hit CTRL+C again to clear the prompt"
                  "\n  * use '%gui none' to disable the event loop"
                  " permanently"
                  "\n    and '%gui qt4' to re-enable it later")
            mgr.clear_inputhook()
        return 0

    def preprompthook_qt4(ishell):
        """'pre_prompt_hook' used to restore the Qt4 input hook

        (in case the latter was temporarily deactivated after a
        CTRL+C)
        """
        if got_kbdint[0]:
            mgr.set_inputhook(inputhook_qt4)
        got_kbdint[0] = False

    ip._inputhook_qt4 = inputhook_qt4
    ip.set_hook('pre_prompt_hook', preprompthook_qt4)

    return app, inputhook_qt4
