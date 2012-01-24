# -*- coding: utf-8 -*-
""" IPython extension: add %clear magic """

import gc

def clear_f(self,arg):
    """ Clear various data (e.g. stored history data)

    %clear in  - clear input history
    %clear out - clear output history
    %clear shadow_compress - Compresses shadow history (to speed up ipython)
    %clear shadow_nuke - permanently erase all entries in shadow history
    %clear dhist - clear dir history
    %clear array - clear only variables that are NumPy arrays

    Examples:

    In [1]: clear in
    Flushing input history

    In [2]: clear shadow_compress
    Compressing shadow history

    In [3]: clear shadow_nuke
    Erased all keys from shadow history

    In [4]: clear dhist
    Clearing directory history
    """

    ip = self.shell
    user_ns = self.user_ns  # local lookup, heavily used


    for target in arg.split():

        if target == 'out':
            print "Flushing output cache (%d entries)" % len(user_ns['_oh'])
            self.displayhook.flush()

        elif target == 'in':
            print "Flushing input history"
            pc = self.displayhook.prompt_count + 1
            for n in range(1, pc):
                key = '_i'+repr(n)
                user_ns.pop(key,None)
            user_ns.update(dict(_i=u'',_ii=u'',_iii=u''))
            # don't delete these, as %save and %macro depending on the length
            # of these lists to be preserved
            self.history_manager.input_hist_parsed[:] = [''] * pc
            self.history_manager.input_hist_raw[:] = [''] * pc

        elif target == 'array':
            # Support cleaning up numpy arrays
            try:
                from numpy import ndarray
                # This must be done with items and not iteritems because we're
                # going to modify the dict in-place.
                for x,val in user_ns.items():
                    if isinstance(val,ndarray):
                        del user_ns[x]
            except ImportError:
                print "Clear array only works if Numpy is available."

        elif target == 'shadow_compress':
            print "Compressing shadow history"
            ip.db.hcompress('shadowhist')

        elif target == 'shadow_nuke':
            print "Erased all keys from shadow history "
            for k in ip.db.keys('shadowhist/*'):
                del ip.db[k]

        elif target == 'dhist':
            print "Clearing directory history"
            del user_ns['_dh'][:]

    gc.collect()

_loaded = False

# Activate the extension
def load_ipython_extension(ip):
    """Load the extension in IPython."""
    global _loaded
    if not _loaded:
        ip.define_magic("clear",clear_f)
        from IPython.core.completerlib import quick_completer
        quick_completer('%clear','in out array shadow_nuke shadow_compress dhist')
