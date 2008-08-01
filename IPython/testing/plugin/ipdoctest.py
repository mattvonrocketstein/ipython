"""Nose Plugin that supports IPython doctests.

Limitations:

- When generating examples for use as doctests, make sure that you have
  pretty-printing OFF.  This can be done either by starting ipython with the
  flag '--nopprint', by setting pprint to 0 in your ipythonrc file, or by
  interactively disabling it with %Pprint.  This is required so that IPython
  output matches that of normal Python, which is used by doctest for internal
  execution.

- Do not rely on specific prompt numbers for results (such as using
  '_34==True', for example).  For IPython tests run via an external process the
  prompt numbers may be different, and IPython tests run as normal python code
  won't even have these special _NN variables set at all.

- IPython functions that produce output as a side-effect of calling a system
  process (e.g. 'ls') can be doc-tested, but they must be handled in an
  external IPython process.  Such doctests must be tagged with:

        # ipdoctest: EXTERNAL

  so that the testing machinery handles them differently.  Since these are run
  via pexpect in an external process, they can't deal with exceptions or other
  fancy featurs of regular doctests.  You must limit such tests to simple
  matching of the output.  For this reason, I recommend you limit these kinds
  of doctests to features that truly require a separate process, and use the
  normal IPython ones (which have all the features of normal doctests) for
  everything else.  See the examples at the bottom of this file for a
  comparison of what can be done with both types.
"""


#-----------------------------------------------------------------------------
# Module imports

# From the standard library
import __builtin__
import commands
import doctest
import inspect
import logging
import os
import re
import sys
import traceback
import unittest

from inspect import getmodule
from StringIO import StringIO

# We are overriding the default doctest runner, so we need to import a few
# things from doctest directly
from doctest import (REPORTING_FLAGS, REPORT_ONLY_FIRST_FAILURE,
                     _unittest_reportflags, DocTestRunner,
                     _extract_future_flags, pdb, _OutputRedirectingPdb,
                     _exception_traceback,
                     linecache)

# Third-party modules
import nose.core

from nose.plugins import doctests, Plugin
from nose.util import anyp, getpackage, test_address, resolve_name, tolist

# Our own imports
#from extdoctest import ExtensionDoctest, DocTestFinder
#from dttools import DocTestFinder, DocTestCase
#-----------------------------------------------------------------------------
# Module globals and other constants

log = logging.getLogger(__name__)

###########################################################################
# *** HACK ***
# We must start our own ipython object and heavily muck with it so that all the
# modifications IPython makes to system behavior don't send the doctest
# machinery into a fit.  This code should be considered a gross hack, but it
# gets the job done.

class ncdict(dict):
    """Non-copying dict class.

    This is a special-purpose dict subclass that overrides the .copy() method
    to return the original object itself.  We need it to ensure that doctests
    happen in the IPython namespace, but doctest always makes a shallow copy of
    the given globals for execution.  Since we actually *want* this namespace
    to be persistent (this is how the user's session maintains state), we
    simply fool doctest by returning the original object upoon copy.
    """
    
    def copy(self):
        return self


# XXX - Hack to modify the %run command so we can sync the user's namespace
# with the test globals.  Once we move over to a clean magic system, this will
# be done with much less ugliness.

def _run_ns_sync(self,arg_s,runner=None):
    """Modified version of %run that syncs testing namespaces.

    This is strictly needed for running doctests that call %run.
    """

    out = _ip.IP.magic_run_ori(arg_s,runner)
    _run_ns_sync.test_globs.update(_ip.user_ns)
    return out


def start_ipython():
    """Start a global IPython shell, which we need for IPython-specific syntax.
    """
    import new

    import IPython

    def xsys(cmd):
        """Execute a command and print its output.

        This is just a convenience function to replace the IPython system call
        with one that is more doctest-friendly.
        """
        cmd = _ip.IP.var_expand(cmd,depth=1)
        sys.stdout.write(commands.getoutput(cmd))
        sys.stdout.flush()

    # Store certain global objects that IPython modifies
    _displayhook = sys.displayhook
    _excepthook = sys.excepthook
    _main = sys.modules.get('__main__')

    # Start IPython instance.  We customize it to start with minimal frills and
    # with our own namespace.
    argv = ['--classic','--noterm_title']
    user_ns = ncdict()
    IPython.Shell.IPShell(argv,user_ns)

    # Deactivate the various python system hooks added by ipython for
    # interactive convenience so we don't confuse the doctest system
    sys.modules['__main__'] = _main
    sys.displayhook = _displayhook
    sys.excepthook = _excepthook

    # So that ipython magics and aliases can be doctested (they work by making
    # a call into a global _ip object)
    _ip = IPython.ipapi.get()
    __builtin__._ip = _ip

    # Modify the IPython system call with one that uses getoutput, so that we
    # can capture subcommands and print them to Python's stdout, otherwise the
    # doctest machinery would miss them.
    _ip.system = xsys

    im = new.instancemethod(_run_ns_sync,_ip.IP, _ip.IP.__class__)
    _ip.IP.magic_run_ori = _ip.IP.magic_run
    _ip.IP.magic_run = im

# The start call MUST be made here.  I'm not sure yet why it doesn't work if
# it is made later, at plugin initialization time, but in all my tests, that's
# the case.
start_ipython()

# *** END HACK ***
###########################################################################

# Classes and functions

def is_extension_module(filename):
    """Return whether the given filename is an extension module.

    This simply checks that the extension is either .so or .pyd.
    """
    return os.path.splitext(filename)[1].lower() in ('.so','.pyd')


# Modified version of the one in the stdlib, that fixes a python bug (doctests
# not found in extension modules, http://bugs.python.org/issue3158)
class DocTestFinder(doctest.DocTestFinder):

    def _from_module(self, module, object):
        """
        Return true if the given object is defined in the given
        module.
        """
        if module is None:
            #print '_fm C1'  # dbg
            return True
        elif inspect.isfunction(object):
            #print '_fm C2'  # dbg
            return module.__dict__ is object.func_globals
        elif inspect.isbuiltin(object):
            #print '_fm C2-1'  # dbg
            return module.__name__ == object.__module__
        elif inspect.isclass(object):
            #print '_fm C3'  # dbg
            return module.__name__ == object.__module__
        elif inspect.ismethod(object):
            # This one may be a bug in cython that fails to correctly set the
            # __module__ attribute of methods, but since the same error is easy
            # to make by extension code writers, having this safety in place
            # isn't such a bad idea
            #print '_fm C3-1'  # dbg
            return module.__name__ == object.im_class.__module__
        elif inspect.getmodule(object) is not None:
            #print '_fm C4'  # dbg
            #print 'C4 mod',module,'obj',object # dbg
            return module is inspect.getmodule(object)
        elif hasattr(object, '__module__'):
            #print '_fm C5'  # dbg
            return module.__name__ == object.__module__
        elif isinstance(object, property):
            #print '_fm C6'  # dbg
            return True # [XX] no way not be sure.
        else:
            raise ValueError("object must be a class or function")

    def _find(self, tests, obj, name, module, source_lines, globs, seen):
        """
        Find tests for the given object and any contained objects, and
        add them to `tests`.
        """

        doctest.DocTestFinder._find(self,tests, obj, name, module,
                                    source_lines, globs, seen)

        # Below we re-run pieces of the above method with manual modifications,
        # because the original code is buggy and fails to correctly identify
        # doctests in extension modules.

        # Local shorthands
        from inspect import isroutine, isclass, ismodule

        # Look for tests in a module's contained objects.
        if inspect.ismodule(obj) and self._recurse:
            for valname, val in obj.__dict__.items():
                valname1 = '%s.%s' % (name, valname)
                if ( (isroutine(val) or isclass(val))
                     and self._from_module(module, val) ):

                    self._find(tests, val, valname1, module, source_lines,
                               globs, seen)

        # Look for tests in a class's contained objects.
        if inspect.isclass(obj) and self._recurse:
            #print 'RECURSE into class:',obj  # dbg
            for valname, val in obj.__dict__.items():
                #valname1 = '%s.%s' % (name, valname)  # dbg
                #print 'N',name,'VN:',valname,'val:',str(val)[:77] # dbg
                # Special handling for staticmethod/classmethod.
                if isinstance(val, staticmethod):
                    val = getattr(obj, valname)
                if isinstance(val, classmethod):
                    val = getattr(obj, valname).im_func

                # Recurse to methods, properties, and nested classes.
                if ((inspect.isfunction(val) or inspect.isclass(val) or
                     inspect.ismethod(val) or
                      isinstance(val, property)) and
                      self._from_module(module, val)):
                    valname = '%s.%s' % (name, valname)
                    self._find(tests, val, valname, module, source_lines,
                               globs, seen)


# second-chance checker; if the default comparison doesn't
# pass, then see if the expected output string contains flags that
# tell us to ignore the output
class IPDoctestOutputChecker(doctest.OutputChecker):
    def check_output(self, want, got, optionflags):
        #print '*** My Checker!'  # dbg

        ret = doctest.OutputChecker.check_output(self, want, got,
                                                 optionflags)
        if not ret:
            if "#random" in want:
                return True

        return ret


class DocTestCase(doctests.DocTestCase):
    """Proxy for DocTestCase: provides an address() method that
    returns the correct address for the doctest case. Otherwise
    acts as a proxy to the test case. To provide hints for address(),
    an obj may also be passed -- this will be used as the test object
    for purposes of determining the test address, if it is provided.
    """

    # Note: this method was taken from numpy's nosetester module.

    # Subclass nose.plugins.doctests.DocTestCase to work around a bug in
    # its constructor that blocks non-default arguments from being passed
    # down into doctest.DocTestCase

    def __init__(self, test, optionflags=0, setUp=None, tearDown=None,
                 checker=None, obj=None, result_var='_'):
        self._result_var = result_var
        doctests.DocTestCase.__init__(self, test,
                                      optionflags=optionflags,
                                      setUp=setUp, tearDown=tearDown,
                                      checker=checker)
        # Now we must actually copy the original constructor from the stdlib
        # doctest class, because we can't call it directly and a bug in nose
        # means it never gets passed the right arguments.

        self._dt_optionflags = optionflags
        self._dt_checker = checker
        self._dt_test = test
        self._dt_setUp = setUp
        self._dt_tearDown = tearDown

    # Modified runTest from the default stdlib
    def runTest(self):
        #print 'HERE!'  # dbg
        
        test = self._dt_test
        old = sys.stdout
        new = StringIO()
        optionflags = self._dt_optionflags

        if not (optionflags & REPORTING_FLAGS):
            # The option flags don't include any reporting flags,
            # so add the default reporting flags
            optionflags |= _unittest_reportflags

        runner = IPDocTestRunner(optionflags=optionflags,
                                 checker=self._dt_checker, verbose=False)

        try:
            runner.DIVIDER = "-"*70
            failures, tries = runner.run(
                test, out=new.write, clear_globs=False)
        finally:
            sys.stdout = old

        if failures:
            raise self.failureException(self.format_failure(new.getvalue()))


# A simple subclassing of the original with a different class name, so we can
# distinguish and treat differently IPython examples from pure python ones.
class IPExample(doctest.Example): pass


class IPExternalExample(doctest.Example):
    """Doctest examples to be run in an external process."""

    def __init__(self, source, want, exc_msg=None, lineno=0, indent=0,
                 options=None):
        # Parent constructor
        doctest.Example.__init__(self,source,want,exc_msg,lineno,indent,options)

        # An EXTRA newline is needed to prevent pexpect hangs
        self.source += '\n'


class IPDocTestParser(doctest.DocTestParser):
    """
    A class used to parse strings containing doctest examples.

    Note: This is a version modified to properly recognize IPython input and
    convert any IPython examples into valid Python ones.
    """
    # This regular expression is used to find doctest examples in a
    # string.  It defines three groups: `source` is the source code
    # (including leading indentation and prompts); `indent` is the
    # indentation of the first (PS1) line of the source code; and
    # `want` is the expected output (including leading indentation).

    # Classic Python prompts or default IPython ones
    _PS1_PY = r'>>>'
    _PS2_PY = r'\.\.\.'

    _PS1_IP = r'In\ \[\d+\]:'
    _PS2_IP = r'\ \ \ \.\.\.+:'

    _RE_TPL = r'''
        # Source consists of a PS1 line followed by zero or more PS2 lines.
        (?P<source>
            (?:^(?P<indent> [ ]*) (?P<ps1> %s) .*)    # PS1 line
            (?:\n           [ ]*  (?P<ps2> %s) .*)*)  # PS2 lines
        \n? # a newline
        # Want consists of any non-blank lines that do not start with PS1.
        (?P<want> (?:(?![ ]*$)    # Not a blank line
                     (?![ ]*%s)   # Not a line starting with PS1
                     (?![ ]*%s)   # Not a line starting with PS2
                     .*$\n?       # But any other line
                  )*)
                  '''

    _EXAMPLE_RE_PY = re.compile( _RE_TPL % (_PS1_PY,_PS2_PY,_PS1_PY,_PS2_PY),
                                 re.MULTILINE | re.VERBOSE)

    _EXAMPLE_RE_IP = re.compile( _RE_TPL % (_PS1_IP,_PS2_IP,_PS1_IP,_PS2_IP),
                                 re.MULTILINE | re.VERBOSE)

    def ip2py(self,source):
        """Convert input IPython source into valid Python."""
        out = []
        newline = out.append
        for lnum,line in enumerate(source.splitlines()):
            newline(_ip.IP.prefilter(line,lnum>0))
        newline('')  # ensure a closing newline, needed by doctest
        #print "PYSRC:", '\n'.join(out)  # dbg
        return '\n'.join(out)

    def parse(self, string, name='<string>'):
        """
        Divide the given string into examples and intervening text,
        and return them as a list of alternating Examples and strings.
        Line numbers for the Examples are 0-based.  The optional
        argument `name` is a name identifying this string, and is only
        used for error messages.
        """

        #print 'Parse string:\n',string # dbg

        string = string.expandtabs()
        # If all lines begin with the same indentation, then strip it.
        min_indent = self._min_indent(string)
        if min_indent > 0:
            string = '\n'.join([l[min_indent:] for l in string.split('\n')])

        output = []
        charno, lineno = 0, 0

        # Whether to convert the input from ipython to python syntax
        ip2py = False
        # Find all doctest examples in the string.  First, try them as Python
        # examples, then as IPython ones
        terms = list(self._EXAMPLE_RE_PY.finditer(string))
        if terms:
            # Normal Python example
            #print '-'*70  # dbg
            #print 'PyExample, Source:\n',string  # dbg
            #print '-'*70  # dbg
            Example = doctest.Example
        else:
            # It's an ipython example.  Note that IPExamples are run
            # in-process, so their syntax must be turned into valid python.
            # IPExternalExamples are run out-of-process (via pexpect) so they
            # don't need any filtering (a real ipython will be executing them).
            terms = list(self._EXAMPLE_RE_IP.finditer(string))
            if re.search(r'#\s*ipdoctest:\s*EXTERNAL',string):
                #print '-'*70  # dbg
                #print 'IPExternalExample, Source:\n',string  # dbg
                #print '-'*70  # dbg
                Example = IPExternalExample
            else:
                #print '-'*70  # dbg
                #print 'IPExample, Source:\n',string  # dbg
                #print '-'*70  # dbg
                Example = IPExample
                ip2py = True

        for m in terms:
            # Add the pre-example text to `output`.
            output.append(string[charno:m.start()])
            # Update lineno (lines before this example)
            lineno += string.count('\n', charno, m.start())
            # Extract info from the regexp match.
            (source, options, want, exc_msg) = \
                     self._parse_example(m, name, lineno,ip2py)
            if Example is IPExternalExample:
                options[doctest.NORMALIZE_WHITESPACE] = True
                want += '\n'
            # Create an Example, and add it to the list.
            if not self._IS_BLANK_OR_COMMENT(source):
                #print 'Example source:', source # dbg
                output.append(Example(source, want, exc_msg,
                                      lineno=lineno,
                                      indent=min_indent+len(m.group('indent')),
                                      options=options))
            # Update lineno (lines inside this example)
            lineno += string.count('\n', m.start(), m.end())
            # Update charno.
            charno = m.end()
        # Add any remaining post-example text to `output`.
        output.append(string[charno:])
        return output

    def _parse_example(self, m, name, lineno,ip2py=False):
        """
        Given a regular expression match from `_EXAMPLE_RE` (`m`),
        return a pair `(source, want)`, where `source` is the matched
        example's source code (with prompts and indentation stripped);
        and `want` is the example's expected output (with indentation
        stripped).

        `name` is the string's name, and `lineno` is the line number
        where the example starts; both are used for error messages.

        Optional:
        `ip2py`: if true, filter the input via IPython to convert the syntax
        into valid python.
        """

        # Get the example's indentation level.
        indent = len(m.group('indent'))

        # Divide source into lines; check that they're properly
        # indented; and then strip their indentation & prompts.
        source_lines = m.group('source').split('\n')

        # We're using variable-length input prompts
        ps1 = m.group('ps1')
        ps2 = m.group('ps2')
        ps1_len = len(ps1)

        self._check_prompt_blank(source_lines, indent, name, lineno,ps1_len)
        if ps2:
            self._check_prefix(source_lines[1:], ' '*indent + ps2, name, lineno)

        source = '\n'.join([sl[indent+ps1_len+1:] for sl in source_lines])

        if ip2py:
            # Convert source input from IPython into valid Python syntax
            source = self.ip2py(source)

        # Divide want into lines; check that it's properly indented; and
        # then strip the indentation.  Spaces before the last newline should
        # be preserved, so plain rstrip() isn't good enough.
        want = m.group('want')
        want_lines = want.split('\n')
        if len(want_lines) > 1 and re.match(r' *$', want_lines[-1]):
            del want_lines[-1]  # forget final newline & spaces after it
        self._check_prefix(want_lines, ' '*indent, name,
                           lineno + len(source_lines))

        # Remove ipython output prompt that might be present in the first line
        want_lines[0] = re.sub(r'Out\[\d+\]: \s*?\n?','',want_lines[0])

        want = '\n'.join([wl[indent:] for wl in want_lines])

        # If `want` contains a traceback message, then extract it.
        m = self._EXCEPTION_RE.match(want)
        if m:
            exc_msg = m.group('msg')
        else:
            exc_msg = None

        # Extract options from the source.
        options = self._find_options(source, name, lineno)

        return source, options, want, exc_msg

    def _check_prompt_blank(self, lines, indent, name, lineno, ps1_len):
        """
        Given the lines of a source string (including prompts and
        leading indentation), check to make sure that every prompt is
        followed by a space character.  If any line is not followed by
        a space character, then raise ValueError.

        Note: IPython-modified version which takes the input prompt length as a
        parameter, so that prompts of variable length can be dealt with.
        """
        space_idx = indent+ps1_len
        min_len = space_idx+1
        for i, line in enumerate(lines):
            if len(line) >=  min_len and line[space_idx] != ' ':
                raise ValueError('line %r of the docstring for %s '
                                 'lacks blank after %s: %r' %
                                 (lineno+i+1, name,
                                  line[indent:space_idx], line))


SKIP = doctest.register_optionflag('SKIP')


class IPDocTestRunner(doctest.DocTestRunner):
    
    # Unfortunately, doctest uses a private method (__run) for the actual run
    # execution, so we can't cleanly override just that part.  Instead, we have
    # to copy/paste the entire run() implementation so we can call our own
    # customized runner.

    #/////////////////////////////////////////////////////////////////
    # DocTest Running
    #/////////////////////////////////////////////////////////////////
    
    __LINECACHE_FILENAME_RE = re.compile(r'<doctest '
                                         r'(?P<name>[\w\.]+)'
                                         r'\[(?P<examplenum>\d+)\]>$')
    
    def __patched_linecache_getlines(self, filename, module_globals=None):
        m = self.__LINECACHE_FILENAME_RE.match(filename)
        if m and m.group('name') == self.test.name:
            example = self.test.examples[int(m.group('examplenum'))]
            return example.source.splitlines(True)
        else:
            return self.save_linecache_getlines(filename, module_globals)


    def _run_ip(self, test, compileflags, out):
        """
        Run the examples in `test`.  Write the outcome of each example
        with one of the `DocTestRunner.report_*` methods, using the
        writer function `out`.  `compileflags` is the set of compiler
        flags that should be used to execute examples.  Return a tuple
        `(f, t)`, where `t` is the number of examples tried, and `f`
        is the number of examples that failed.  The examples are run
        in the namespace `test.globs`.
        """

        #print 'Custom ip runner! __run' # dbg

        # Keep track of the number of failures and tries.
        failures = tries = 0

        # Save the option flags (since option directives can be used
        # to modify them).
        original_optionflags = self.optionflags

        SUCCESS, FAILURE, BOOM = range(3) # `outcome` state

        check = self._checker.check_output

        # Process each example.
        for examplenum, example in enumerate(test.examples):

            # If REPORT_ONLY_FIRST_FAILURE is set, then supress
            # reporting after the first failure.
            quiet = (self.optionflags & REPORT_ONLY_FIRST_FAILURE and
                     failures > 0)

            # Merge in the example's options.
            self.optionflags = original_optionflags
            if example.options:
                for (optionflag, val) in example.options.items():
                    if val:
                        self.optionflags |= optionflag
                    else:
                        self.optionflags &= ~optionflag

            # If 'SKIP' is set, then skip this example.
            if self.optionflags & SKIP:
                continue

            # Record that we started this example.
            tries += 1
            if not quiet:
                self.report_start(out, test, example)

            # Use a special filename for compile(), so we can retrieve
            # the source code during interactive debugging (see
            # __patched_linecache_getlines).
            filename = '<doctest %s[%d]>' % (test.name, examplenum)

            # Run the example in the given context (globs), and record
            # any exception that gets raised.  (But don't intercept
            # keyboard interrupts.)
            try:
                # Don't blink!  This is where the user's code gets run.

                # Hack: ipython needs access to the execution context of the
                # example, so that it can propagate user variables loaded by
                # %run into test.globs.  We put them here into our modified
                # %run as a function attribute.  Our new %run will then only
                # make the namespace update when called (rather than
                # unconconditionally updating test.globs here for all examples,
                # most of which won't be calling %run anyway).
                _run_ns_sync.test_globs = test.globs
                
                exec compile(example.source, filename, "single",
                             compileflags, 1) in test.globs
                self.debugger.set_continue() # ==== Example Finished ====
                exception = None
            except KeyboardInterrupt:
                raise
            except:
                exception = sys.exc_info()
                self.debugger.set_continue() # ==== Example Finished ====

            got = self._fakeout.getvalue()  # the actual output
            self._fakeout.truncate(0)
            outcome = FAILURE   # guilty until proved innocent or insane

            # If the example executed without raising any exceptions,
            # verify its output.
            if exception is None:
                if check(example.want, got, self.optionflags):
                    outcome = SUCCESS

            # The example raised an exception:  check if it was expected.
            else:
                exc_info = sys.exc_info()
                exc_msg = traceback.format_exception_only(*exc_info[:2])[-1]
                if not quiet:
                    got += _exception_traceback(exc_info)

                # If `example.exc_msg` is None, then we weren't expecting
                # an exception.
                if example.exc_msg is None:
                    outcome = BOOM

                # We expected an exception:  see whether it matches.
                elif check(example.exc_msg, exc_msg, self.optionflags):
                    outcome = SUCCESS

                # Another chance if they didn't care about the detail.
                elif self.optionflags & IGNORE_EXCEPTION_DETAIL:
                    m1 = re.match(r'[^:]*:', example.exc_msg)
                    m2 = re.match(r'[^:]*:', exc_msg)
                    if m1 and m2 and check(m1.group(0), m2.group(0),
                                           self.optionflags):
                        outcome = SUCCESS

            # Report the outcome.
            if outcome is SUCCESS:
                if not quiet:
                    self.report_success(out, test, example, got)
            elif outcome is FAILURE:
                if not quiet:
                    self.report_failure(out, test, example, got)
                failures += 1
            elif outcome is BOOM:
                if not quiet:
                    self.report_unexpected_exception(out, test, example,
                                                     exc_info)
                failures += 1
            else:
                assert False, ("unknown outcome", outcome)

        # Restore the option flags (in case they were modified)
        self.optionflags = original_optionflags

        # Record and return the number of failures and tries.

        # Hack to access a parent private method by working around Python's
        # name mangling (which is fortunately simple).
        #self.__record_outcome(test, failures, tries)
        doctest.DocTestRunner._DocTestRunner__record_outcome(self,test,
                                                             failures, tries)

        return failures, tries


    # Unfortunately doctest has chosen to implement a couple of key methods as
    # private (__run, in particular).  We are forced to copy the entire run
    # method here just so we can override that one.  Ugh.
    
    def run(self, test, compileflags=None, out=None, clear_globs=True):
        """
        Run the examples in `test`, and display the results using the
        writer function `out`.

        The examples are run in the namespace `test.globs`.  If
        `clear_globs` is true (the default), then this namespace will
        be cleared after the test runs, to help with garbage
        collection.  If you would like to examine the namespace after
        the test completes, then use `clear_globs=False`.

        `compileflags` gives the set of flags that should be used by
        the Python compiler when running the examples.  If not
        specified, then it will default to the set of future-import
        flags that apply to `globs`.

        The output of each example is checked using
        `DocTestRunner.check_output`, and the results are formatted by
        the `DocTestRunner.report_*` methods.
        """
        #print 'Custom ip runner!' # dbg
    
        self.test = test

        if compileflags is None:
            compileflags = _extract_future_flags(test.globs)

        save_stdout = sys.stdout
        if out is None:
            out = save_stdout.write
        sys.stdout = self._fakeout

        # Patch pdb.set_trace to restore sys.stdout during interactive
        # debugging (so it's not still redirected to self._fakeout).
        # Note that the interactive output will go to *our*
        # save_stdout, even if that's not the real sys.stdout; this
        # allows us to write test cases for the set_trace behavior.
        save_set_trace = pdb.set_trace
        self.debugger = _OutputRedirectingPdb(save_stdout)
        self.debugger.reset()
        pdb.set_trace = self.debugger.set_trace

        # Patch linecache.getlines, so we can see the example's source
        # when we're inside the debugger.
        self.save_linecache_getlines = linecache.getlines
        linecache.getlines = self.__patched_linecache_getlines

        try:
            # Hack to access a parent private method by working around Python's
            # name mangling (which is fortunately simple).
            #return self.__run(test, compileflags, out)
            return self._run_ip(test, compileflags, out)
            #return doctest.DocTestRunner._DocTestRunner__run(self,test,
            #                                                 compileflags, out)
        finally:
            _ip.user_ns.update(test.globs)
            sys.stdout = save_stdout
            pdb.set_trace = save_set_trace
            linecache.getlines = self.save_linecache_getlines
            if clear_globs:
                test.globs.clear()


class DocFileCase(doctest.DocFileCase):
    """Overrides to provide filename
    """
    def address(self):
        return (self._dt_test.filename, None, None)


class ExtensionDoctest(doctests.Doctest):
    """Nose Plugin that supports doctests in extension modules.
    """
    name = 'extdoctest'   # call nosetests with --with-extdoctest
    enabled = True

    def options(self, parser, env=os.environ):
        Plugin.options(self, parser, env)

    def configure(self, options, config):
        Plugin.configure(self, options, config)
        self.doctest_tests = options.doctest_tests
        self.extension = tolist(options.doctestExtension)
        self.finder = DocTestFinder()
        self.parser = doctest.DocTestParser()
        self.globs = None
        self.extraglobs = None

    def loadTestsFromExtensionModule(self,filename):
        bpath,mod = os.path.split(filename)
        modname = os.path.splitext(mod)[0]
        try:
            sys.path.append(bpath)
            module = __import__(modname)
            tests = list(self.loadTestsFromModule(module))
        finally:
            sys.path.pop()
        return tests

    # NOTE: the method below is almost a copy of the original one in nose, with
    # a  few modifications to control output checking.

    def loadTestsFromModule(self, module):
        #print 'lTM',module  # dbg

        if not self.matches(module.__name__):
            log.debug("Doctest doesn't want module %s", module)
            return

        ## try:
        ##     print 'Globs:',self.globs.keys() # dbg
        ## except:
        ##     pass
        
        tests = self.finder.find(module,globs=self.globs,
                                 extraglobs=self.extraglobs)
        if not tests:
            return
        tests.sort()
        module_file = module.__file__
        if module_file[-4:] in ('.pyc', '.pyo'):
            module_file = module_file[:-1]
        for test in tests:
            if not test.examples:
                continue
            if not test.filename:
                test.filename = module_file

            # xxx - checker and options may be ok instantiated once outside loop

            # always use whitespace and ellipsis options
            optionflags = doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
            checker = IPDoctestOutputChecker()
            
            yield DocTestCase(test,
                              optionflags=optionflags,
                              checker=checker)

    def loadTestsFromFile(self, filename):
        #print 'lTF',filename  # dbg

        if is_extension_module(filename):
            for t in self.loadTestsFromExtensionModule(filename):
                yield t
        else:
            if self.extension and anyp(filename.endswith, self.extension):
                name = os.path.basename(filename)
                dh = open(filename)
                try:
                    doc = dh.read()
                finally:
                    dh.close()
                test = self.parser.get_doctest(
                    doc, globs={'__file__': filename}, name=name,
                    filename=filename, lineno=0)
                if test.examples:
                    #print 'FileCase:',test.examples  # dbg
                    yield DocFileCase(test)
                else:
                    yield False # no tests to load

    def wantFile(self,filename):
        """Return whether the given filename should be scanned for tests.

        Modified version that accepts extension modules as valid containers for
        doctests.
        """
        #print 'Filename:',filename  # dbg

        # temporarily hardcoded list, will move to driver later
        exclude = ['IPython/external/',
                   'IPython/Extensions/ipy_',
                   'IPython/platutils_win32',
                   'IPython/frontend/cocoa',
                   'IPython_doctest_plugin',
                   'IPython/Gnuplot',
                   'IPython/Extensions/PhysicalQIn']

        for fex in exclude:
            if fex in filename:  # substring
                #print '###>>> SKIP:',filename  # dbg
                return False

        if is_extension_module(filename):
            return True
        else:
            return doctests.Doctest.wantFile(self,filename)


class IPythonDoctest(ExtensionDoctest):
    """Nose Plugin that supports doctests in extension modules.
    """
    name = 'ipdoctest'   # call nosetests with --with-ipdoctest
    enabled = True

    def configure(self, options, config):

        Plugin.configure(self, options, config)
        self.doctest_tests = options.doctest_tests
        self.extension = tolist(options.doctestExtension)
        self.parser = IPDocTestParser()
        self.finder = DocTestFinder(parser=self.parser)

        # XXX - we need to run in the ipython user's namespace, but doing so is
        # breaking normal doctests!
        
        #self.globs = _ip.user_ns
        self.globs = None
        
        self.extraglobs = None

        # Use a specially modified test runner that is IPython-aware
        self.iprunner = None
