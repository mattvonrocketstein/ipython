#!/usr/bin/env python

""" A minimal application using the Qt console-style IPython frontend.
"""

# Systemm library imports
from PyQt4 import QtCore, QtGui

# Local imports
from IPython.external.argparse import ArgumentParser
from IPython.frontend.qt.console.frontend_widget import FrontendWidget
from IPython.frontend.qt.console.ipython_widget import IPythonWidget
from IPython.frontend.qt.console.rich_ipython_widget import RichIPythonWidget
from IPython.frontend.qt.kernelmanager import QtKernelManager

# Constants
LOCALHOST = '127.0.0.1'


def main():
    """ Entry point for application.
    """
    # Parse command line arguments.
    parser = ArgumentParser()
    kgroup = parser.add_argument_group('kernel options')
    kgroup.add_argument('-e', '--existing', action='store_true',
                        help='connect to an existing kernel')
    kgroup.add_argument('--ip', type=str, default=LOCALHOST,
                        help='set the kernel\'s IP address [default localhost]')
    kgroup.add_argument('--xreq', type=int, metavar='PORT', default=0,
                        help='set the XREQ channel port [default random]')
    kgroup.add_argument('--sub', type=int, metavar='PORT', default=0,
                        help='set the SUB channel port [default random]')
    kgroup.add_argument('--rep', type=int, metavar='PORT', default=0,
                        help='set the REP channel port [default random]')

    egroup = kgroup.add_mutually_exclusive_group()
    egroup.add_argument('--pure', action='store_true', help = \
                        'use a pure Python kernel instead of an IPython kernel')
    egroup.add_argument('--pylab', action='store_true',
                        help='use a kernel with PyLab enabled')

    wgroup = parser.add_argument_group('widget options')
    wgroup.add_argument('--paging', type=str, default='inside',
                        choices = ['inside', 'hsplit', 'vsplit', 'none'],
                        help='set the paging style [default inside]')
    wgroup.add_argument('--rich', action='store_true',
                        help='enable rich text support')
    wgroup.add_argument('--tab-simple', action='store_true',
                        help='do tab completion ala a Unix terminal')
    
    args = parser.parse_args()
    
    # Don't let Qt or ZMQ swallow KeyboardInterupts.
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Create a KernelManager and start a kernel.
    kernel_manager = QtKernelManager(xreq_address=(args.ip, args.xreq),
                                     sub_address=(args.ip, args.sub),
                                     rep_address=(args.ip, args.rep))
    if args.ip == LOCALHOST and not args.existing:
        if args.pure:
            kernel_manager.start_kernel(ipython=False)
        elif args.pylab:
            if args.rich:
                kernel_manager.start_kernel(pylab='payload-svg')
            else:
                kernel_manager.start_kernel(pylab='qt4')
        else:
            kernel_manager.start_kernel()
    kernel_manager.start_channels()

    # Create the widget.
    app = QtGui.QApplication([])
    if args.pure:
        kind = 'rich' if args.rich else 'plain'
        widget = FrontendWidget(kind=kind, paging=args.paging)
    elif args.rich:
        widget = RichIPythonWidget(paging=args.paging)
    else:
        widget = IPythonWidget(paging=args.paging)
    widget.gui_completion = not args.tab_simple
    widget.kernel_manager = kernel_manager
    widget.setWindowTitle('Python' if args.pure else 'IPython')
    widget.show()

    # Start the application main loop.
    app.exec_()


if __name__ == '__main__':
    main()
