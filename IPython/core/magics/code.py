"""Implementation of code management magic functions.
"""
#-----------------------------------------------------------------------------
#  Copyright (c) 2012 The IPython Development Team.
#
#  Distributed under the terms of the Modified BSD License.
#
#  The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

# Stdlib
import inspect
import io
import json
import os
import sys
from urllib2 import urlopen

# Our own packages
from IPython.core.error import TryNext
from IPython.core.macro import Macro
from IPython.core.magic import Magics, magics_class, line_magic
from IPython.testing.skipdoctest import skip_doctest
from IPython.utils import openpy
from IPython.utils import py3compat
from IPython.utils.io import file_read
from IPython.utils.path import get_py_filename, unquote_filename
from IPython.utils.warn import warn

#-----------------------------------------------------------------------------
# Magic implementation classes
#-----------------------------------------------------------------------------

# Used for exception handling in magic_edit
class MacroToEdit(ValueError): pass


@magics_class
class CodeMagics(Magics):
    """Magics related to code management (loading, saving, editing, ...)."""

    @line_magic
    def save(self, parameter_s=''):
        """Save a set of lines or a macro to a given filename.

        Usage:\\
          %save [options] filename n1-n2 n3-n4 ... n5 .. n6 ...

        Options:

          -r: use 'raw' input.  By default, the 'processed' history is used,
          so that magics are loaded in their transformed version to valid
          Python.  If this option is given, the raw input as typed as the
          command line is used instead.

        This function uses the same syntax as %history for input ranges,
        then saves the lines to the filename you specify.

        It adds a '.py' extension to the file if you don't do so yourself, and
        it asks for confirmation before overwriting existing files."""

        opts,args = self.parse_options(parameter_s,'r',mode='list')
        fname, codefrom = unquote_filename(args[0]), " ".join(args[1:])
        if not fname.endswith('.py'):
            fname += '.py'
        if os.path.isfile(fname):
            ans = raw_input('File `%s` exists. Overwrite (y/[N])? ' % fname)
            if ans.lower() not in ['y','yes']:
                print 'Operation cancelled.'
                return
        try:
            cmds = self.shell.find_user_code(codefrom, 'r' in opts)
        except (TypeError, ValueError) as e:
            print e.args[0]
            return
        with io.open(fname,'w', encoding="utf-8") as f:
            f.write(u"# coding: utf-8\n")
            f.write(py3compat.cast_unicode(cmds))
        print 'The following commands were written to file `%s`:' % fname
        print cmds

    @line_magic
    def pastebin(self, parameter_s=''):
        """Upload code to Github's Gist paste bin, returning the URL.

        Usage:\\
          %pastebin [-d "Custom description"] 1-7

        The argument can be an input history range, a filename, or the name of a
        string or macro.

        Options:

          -d: Pass a custom description for the gist. The default will say
              "Pasted from IPython".
        """
        opts, args = self.parse_options(parameter_s, 'd:')

        try:
            code = self.shell.find_user_code(args)
        except (ValueError, TypeError) as e:
            print e.args[0]
            return

        post_data = json.dumps({
          "description": opts.get('d', "Pasted from IPython"),
          "public": True,
          "files": {
            "file1.py": {
              "content": code
            }
          }
        }).encode('utf-8')

        response = urlopen("https://api.github.com/gists", post_data)
        response_data = json.loads(response.read().decode('utf-8'))
        return response_data['html_url']

    @line_magic
    def loadpy(self, arg_s):
        """Load a .py python script into the GUI console.

        This magic command can either take a local filename or a url::

        %loadpy myscript.py
        %loadpy http://www.example.com/myscript.py
        """
        arg_s = unquote_filename(arg_s)
        remote_url = arg_s.startswith(('http://', 'https://'))
        local_url = not remote_url
        if local_url and not arg_s.endswith('.py'):
            # Local files must be .py; for remote URLs it's possible that the
            # fetch URL doesn't have a .py in it (many servers have an opaque
            # URL, such as scipy-central.org).
            raise ValueError('%%loadpy only works with .py files: %s' % arg_s)

        # openpy takes care of finding the source encoding (per PEP 263)
        if remote_url:
            contents = openpy.read_py_url(arg_s, skip_encoding_cookie=True)
        else:
            contents = openpy.read_py_file(arg_s, skip_encoding_cookie=True)

        self.shell.set_next_input(contents)

    def _find_edit_target(self, args, opts, last_call):
        """Utility method used by magic_edit to find what to edit."""

        def make_filename(arg):
            "Make a filename from the given args"
            arg = unquote_filename(arg)
            try:
                filename = get_py_filename(arg)
            except IOError:
                # If it ends with .py but doesn't already exist, assume we want
                # a new file.
                if arg.endswith('.py'):
                    filename = arg
                else:
                    filename = None
            return filename

        # Set a few locals from the options for convenience:
        opts_prev = 'p' in opts
        opts_raw = 'r' in opts

        # custom exceptions
        class DataIsObject(Exception): pass

        # Default line number value
        lineno = opts.get('n',None)

        if opts_prev:
            args = '_%s' % last_call[0]
            if not self.shell.user_ns.has_key(args):
                args = last_call[1]

        # use last_call to remember the state of the previous call, but don't
        # let it be clobbered by successive '-p' calls.
        try:
            last_call[0] = self.shell.displayhook.prompt_count
            if not opts_prev:
                last_call[1] = args
        except:
            pass

        # by default this is done with temp files, except when the given
        # arg is a filename
        use_temp = True

        data = ''

        # First, see if the arguments should be a filename.
        filename = make_filename(args)
        if filename:
            use_temp = False
        elif args:
            # Mode where user specifies ranges of lines, like in %macro.
            data = self.shell.extract_input_lines(args, opts_raw)
            if not data:
                try:
                    # Load the parameter given as a variable. If not a string,
                    # process it as an object instead (below)

                    #print '*** args',args,'type',type(args)  # dbg
                    data = eval(args, self.shell.user_ns)
                    if not isinstance(data, basestring):
                        raise DataIsObject

                except (NameError,SyntaxError):
                    # given argument is not a variable, try as a filename
                    filename = make_filename(args)
                    if filename is None:
                        warn("Argument given (%s) can't be found as a variable "
                             "or as a filename." % args)
                        return
                    use_temp = False

                except DataIsObject:
                    # macros have a special edit function
                    if isinstance(data, Macro):
                        raise MacroToEdit(data)

                    # For objects, try to edit the file where they are defined
                    try:
                        filename = inspect.getabsfile(data)
                        if 'fakemodule' in filename.lower() and \
                            inspect.isclass(data):
                            # class created by %edit? Try to find source
                            # by looking for method definitions instead, the
                            # __module__ in those classes is FakeModule.
                            attrs = [getattr(data, aname) for aname in dir(data)]
                            for attr in attrs:
                                if not inspect.ismethod(attr):
                                    continue
                                filename = inspect.getabsfile(attr)
                                if filename and \
                                  'fakemodule' not in filename.lower():
                                    # change the attribute to be the edit
                                    # target instead
                                    data = attr
                                    break

                        datafile = 1
                    except TypeError:
                        filename = make_filename(args)
                        datafile = 1
                        warn('Could not find file where `%s` is defined.\n'
                             'Opening a file named `%s`' % (args, filename))
                    # Now, make sure we can actually read the source (if it was
                    # in a temp file it's gone by now).
                    if datafile:
                        try:
                            if lineno is None:
                                lineno = inspect.getsourcelines(data)[1]
                        except IOError:
                            filename = make_filename(args)
                            if filename is None:
                                warn('The file `%s` where `%s` was defined '
                                     'cannot be read.' % (filename, data))
                                return
                    use_temp = False

        if use_temp:
            filename = self.shell.mktempfile(data)
            print 'IPython will make a temporary file named:',filename

        return filename, lineno, use_temp

    def _edit_macro(self,mname,macro):
        """open an editor with the macro data in a file"""
        filename = self.shell.mktempfile(macro.value)
        self.shell.hooks.editor(filename)

        # and make a new macro object, to replace the old one
        mfile = open(filename)
        mvalue = mfile.read()
        mfile.close()
        self.shell.user_ns[mname] = Macro(mvalue)

    @line_magic
    def ed(self, parameter_s=''):
        """Alias to %edit."""
        return self.edit(parameter_s)

    @skip_doctest
    @line_magic
    def edit(self, parameter_s='',last_call=['','']):
        """Bring up an editor and execute the resulting code.

        Usage:
          %edit [options] [args]

        %edit runs IPython's editor hook. The default version of this hook is
        set to call the editor specified by your $EDITOR environment variable.
        If this isn't found, it will default to vi under Linux/Unix and to
        notepad under Windows. See the end of this docstring for how to change
        the editor hook.

        You can also set the value of this editor via the
        ``TerminalInteractiveShell.editor`` option in your configuration file.
        This is useful if you wish to use a different editor from your typical
        default with IPython (and for Windows users who typically don't set
        environment variables).

        This command allows you to conveniently edit multi-line code right in
        your IPython session.

        If called without arguments, %edit opens up an empty editor with a
        temporary file and will execute the contents of this file when you
        close it (don't forget to save it!).


        Options:

        -n <number>: open the editor at a specified line number.  By default,
        the IPython editor hook uses the unix syntax 'editor +N filename', but
        you can configure this by providing your own modified hook if your
        favorite editor supports line-number specifications with a different
        syntax.

        -p: this will call the editor with the same data as the previous time
        it was used, regardless of how long ago (in your current session) it
        was.

        -r: use 'raw' input.  This option only applies to input taken from the
        user's history.  By default, the 'processed' history is used, so that
        magics are loaded in their transformed version to valid Python.  If
        this option is given, the raw input as typed as the command line is
        used instead.  When you exit the editor, it will be executed by
        IPython's own processor.

        -x: do not execute the edited code immediately upon exit. This is
        mainly useful if you are editing programs which need to be called with
        command line arguments, which you can then do using %run.


        Arguments:

        If arguments are given, the following possibilities exist:

        - If the argument is a filename, IPython will load that into the
          editor. It will execute its contents with execfile() when you exit,
          loading any code in the file into your interactive namespace.

        - The arguments are ranges of input history,  e.g. "7 ~1/4-6".
          The syntax is the same as in the %history magic.

        - If the argument is a string variable, its contents are loaded
          into the editor. You can thus edit any string which contains
          python code (including the result of previous edits).

        - If the argument is the name of an object (other than a string),
          IPython will try to locate the file where it was defined and open the
          editor at the point where it is defined. You can use `%edit function`
          to load an editor exactly at the point where 'function' is defined,
          edit it and have the file be executed automatically.

        - If the object is a macro (see %macro for details), this opens up your
          specified editor with a temporary file containing the macro's data.
          Upon exit, the macro is reloaded with the contents of the file.

        Note: opening at an exact line is only supported under Unix, and some
        editors (like kedit and gedit up to Gnome 2.8) do not understand the
        '+NUMBER' parameter necessary for this feature. Good editors like
        (X)Emacs, vi, jed, pico and joe all do.

        After executing your code, %edit will return as output the code you
        typed in the editor (except when it was an existing file). This way
        you can reload the code in further invocations of %edit as a variable,
        via _<NUMBER> or Out[<NUMBER>], where <NUMBER> is the prompt number of
        the output.

        Note that %edit is also available through the alias %ed.

        This is an example of creating a simple function inside the editor and
        then modifying it. First, start up the editor::

          In [1]: ed
          Editing... done. Executing edited code...
          Out[1]: 'def foo():\\n    print "foo() was defined in an editing
          session"\\n'

        We can then call the function foo()::

          In [2]: foo()
          foo() was defined in an editing session

        Now we edit foo.  IPython automatically loads the editor with the
        (temporary) file where foo() was previously defined::

          In [3]: ed foo
          Editing... done. Executing edited code...

        And if we call foo() again we get the modified version::

          In [4]: foo()
          foo() has now been changed!

        Here is an example of how to edit a code snippet successive
        times. First we call the editor::

          In [5]: ed
          Editing... done. Executing edited code...
          hello
          Out[5]: "print 'hello'\\n"

        Now we call it again with the previous output (stored in _)::

          In [6]: ed _
          Editing... done. Executing edited code...
          hello world
          Out[6]: "print 'hello world'\\n"

        Now we call it with the output #8 (stored in _8, also as Out[8])::

          In [7]: ed _8
          Editing... done. Executing edited code...
          hello again
          Out[7]: "print 'hello again'\\n"


        Changing the default editor hook:

        If you wish to write your own editor hook, you can put it in a
        configuration file which you load at startup time.  The default hook
        is defined in the IPython.core.hooks module, and you can use that as a
        starting example for further modifications.  That file also has
        general instructions on how to set a new hook for use once you've
        defined it."""
        opts,args = self.parse_options(parameter_s,'prxn:')

        try:
            filename, lineno, is_temp = self._find_edit_target(args, opts, last_call)
        except MacroToEdit as e:
            self._edit_macro(args, e.args[0])
            return

        # do actual editing here
        print 'Editing...',
        sys.stdout.flush()
        try:
            # Quote filenames that may have spaces in them
            if ' ' in filename:
                filename = "'%s'" % filename
            self.shell.hooks.editor(filename,lineno)
        except TryNext:
            warn('Could not open editor')
            return

        # XXX TODO: should this be generalized for all string vars?
        # For now, this is special-cased to blocks created by cpaste
        if args.strip() == 'pasted_block':
            self.shell.user_ns['pasted_block'] = file_read(filename)

        if 'x' in opts:  # -x prevents actual execution
            print
        else:
            print 'done. Executing edited code...'
            if 'r' in opts:    # Untranslated IPython code
                self.shell.run_cell(file_read(filename),
                                                    store_history=False)
            else:
                self.shell.safe_execfile(filename, self.shell.user_ns,
                                         self.shell.user_ns)

        if is_temp:
            try:
                return open(filename).read()
            except IOError,msg:
                if msg.filename == filename:
                    warn('File not found. Did you forget to save?')
                    return
                else:
                    self.shell.showtraceback()
