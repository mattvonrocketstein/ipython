import abc
import functools
import re
from StringIO import StringIO
import tokenize

try:
    generate_tokens = tokenize.generate_tokens
except AttributeError:
    # Python 3. Note that we use the undocumented _tokenize because it expects
    # strings, not bytes. See also Python issue #9969.
    generate_tokens = tokenize._tokenize

from IPython.core.splitinput import split_user_input, LineInfo
from IPython.utils.untokenize import untokenize

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------

# The escape sequences that define the syntax transformations IPython will
# apply to user input.  These can NOT be just changed here: many regular
# expressions and other parts of the code may use their hardcoded values, and
# for all intents and purposes they constitute the 'IPython syntax', so they
# should be considered fixed.

ESC_SHELL  = '!'     # Send line to underlying system shell
ESC_SH_CAP = '!!'    # Send line to system shell and capture output
ESC_HELP   = '?'     # Find information about object
ESC_HELP2  = '??'    # Find extra-detailed information about object
ESC_MAGIC  = '%'     # Call magic function
ESC_MAGIC2 = '%%'    # Call cell-magic function
ESC_QUOTE  = ','     # Split args on whitespace, quote each as string and call
ESC_QUOTE2 = ';'     # Quote all args as a single string, call
ESC_PAREN  = '/'     # Call first argument with rest of line as arguments

ESC_SEQUENCES = [ESC_SHELL, ESC_SH_CAP, ESC_HELP ,\
                 ESC_HELP2, ESC_MAGIC, ESC_MAGIC2,\
                 ESC_QUOTE, ESC_QUOTE2, ESC_PAREN ]


class InputTransformer(object):
    """Abstract base class for line-based input transformers."""
    __metaclass__ = abc.ABCMeta
    
    @abc.abstractmethod
    def push(self, line):
        """Send a line of input to the transformer, returning the transformed
        input or None if the transformer is waiting for more input.
        
        Must be overridden by subclasses.
        """
        pass
    
    @abc.abstractmethod
    def reset(self):
        """Return, transformed any lines that the transformer has accumulated,
        and reset its internal state.
        
        Must be overridden by subclasses.
        """
        pass
    
    # Set this to True to allow the transformer to act on lines inside strings.
    look_in_string = False
    
    @classmethod
    def wrap(cls, func):
        """Can be used by subclasses as a decorator, to return a factory that
        will allow instantiation with the decorated object.
        """
        @functools.wraps(func)
        def transformer_factory():
            transformer = cls(func)
            if getattr(transformer_factory, 'look_in_string', False):
                transformer.look_in_string = True
            return transformer
        
        return transformer_factory

class StatelessInputTransformer(InputTransformer):
    """Wrapper for a stateless input transformer implemented as a function."""
    def __init__(self, func):
        self.func = func
    
    def __repr__(self):
        return "StatelessInputTransformer(func={!r})".format(self.func)
    
    def push(self, line):
        """Send a line of input to the transformer, returning the
        transformed input."""
        return self.func(line)
    
    def reset(self):
        """No-op - exists for compatibility."""
        pass

class CoroutineInputTransformer(InputTransformer):
    """Wrapper for an input transformer implemented as a coroutine."""
    def __init__(self, coro):
        # Prime it
        self.coro = coro()
        next(self.coro)
    
    def __repr__(self):
        return "CoroutineInputTransformer(coro={!r})".format(self.coro)
    
    def push(self, line):
        """Send a line of input to the transformer, returning the
        transformed input or None if the transformer is waiting for more
        input.
        """
        return self.coro.send(line)
    
    def reset(self):
        """Return, transformed any lines that the transformer has
        accumulated, and reset its internal state.
        """
        return self.coro.send(None)

class TokenInputTransformer(InputTransformer):
    """Wrapper for a token-based input transformer.
    
    func should accept a list of tokens (5-tuples, see tokenize docs), and
    return an iterable which can be passed to tokenize.untokenize().
    """
    def __init__(self, func):
        self.func = func
        self.current_line = ""
        self.line_used= False
        self.reset_tokenizer()
    
    def reset_tokenizer(self):
        self.tokenizer = generate_tokens(self.get_line)
    
    def get_line(self):
        if self.line_used:
            raise tokenize.TokenError
        self.line_used = True
        return self.current_line
    
    def push(self, line):
        self.current_line += line + "\n"
        self.line_used = False
        tokens = []
        try:
            for intok in self.tokenizer:
                tokens.append(intok)
                if intok[0] in (tokenize.NEWLINE, tokenize.NL):
                    # Stop before we try to pull a line we don't have yet
                    break
        except tokenize.TokenError:
            # Multi-line statement - stop and try again with the next line
            self.reset_tokenizer()
            return None
        
        self.current_line = ""
        self.reset_tokenizer()
        return untokenize(self.func(tokens)).rstrip('\n')
    
    def reset(self):
        l = self.current_line
        self.current_line = ""
        if l:
            return l.rstrip('\n')

@TokenInputTransformer.wrap
def assemble_logical_lines(tokens):
    return tokens

# Utilities
def _make_help_call(target, esc, lspace, next_input=None):
    """Prepares a pinfo(2)/psearch call from a target name and the escape
    (i.e. ? or ??)"""
    method  = 'pinfo2' if esc == '??' \
                else 'psearch' if '*' in target \
                else 'pinfo'
    arg = " ".join([method, target])
    if next_input is None:
        return '%sget_ipython().magic(%r)' % (lspace, arg)
    else:
        return '%sget_ipython().set_next_input(%r);get_ipython().magic(%r)' % \
           (lspace, next_input, arg)

@CoroutineInputTransformer.wrap
def escaped_transformer():
    """Translate lines beginning with one of IPython's escape characters.
    
    This is stateful to allow magic commands etc. to be continued over several
    lines using explicit line continuations (\ at the end of a line).
    """
    
    # These define the transformations for the different escape characters.
    def _tr_system(line_info):
        "Translate lines escaped with: !"
        cmd = line_info.line.lstrip().lstrip(ESC_SHELL)
        return '%sget_ipython().system(%r)' % (line_info.pre, cmd)

    def _tr_system2(line_info):
        "Translate lines escaped with: !!"
        cmd = line_info.line.lstrip()[2:]
        return '%sget_ipython().getoutput(%r)' % (line_info.pre, cmd)

    def _tr_help(line_info):
        "Translate lines escaped with: ?/??"
        # A naked help line should just fire the intro help screen
        if not line_info.line[1:]:
            return 'get_ipython().show_usage()'

        return _make_help_call(line_info.ifun, line_info.esc, line_info.pre)

    def _tr_magic(line_info):
        "Translate lines escaped with: %"
        tpl = '%sget_ipython().magic(%r)'
        cmd = ' '.join([line_info.ifun, line_info.the_rest]).strip()
        return tpl % (line_info.pre, cmd)

    def _tr_quote(line_info):
        "Translate lines escaped with: ,"
        return '%s%s("%s")' % (line_info.pre, line_info.ifun,
                             '", "'.join(line_info.the_rest.split()) )

    def _tr_quote2(line_info):
        "Translate lines escaped with: ;"
        return '%s%s("%s")' % (line_info.pre, line_info.ifun,
                               line_info.the_rest)

    def _tr_paren(line_info):
        "Translate lines escaped with: /"
        return '%s%s(%s)' % (line_info.pre, line_info.ifun,
                             ", ".join(line_info.the_rest.split()))
    
    tr = { ESC_SHELL  : _tr_system,
           ESC_SH_CAP : _tr_system2,
           ESC_HELP   : _tr_help,
           ESC_HELP2  : _tr_help,
           ESC_MAGIC  : _tr_magic,
           ESC_QUOTE  : _tr_quote,
           ESC_QUOTE2 : _tr_quote2,
           ESC_PAREN  : _tr_paren }
    
    line = ''
    while True:
        line = (yield line)
        if not line or line.isspace():
            continue
        lineinf = LineInfo(line)
        if lineinf.esc not in tr:
            continue
        
        parts = []
        while line is not None:
            parts.append(line.rstrip('\\'))
            if not line.endswith('\\'):
                break
            line = (yield None)
        
        # Output
        lineinf = LineInfo(' '.join(parts))
        line = tr[lineinf.esc](lineinf)

_initial_space_re = re.compile(r'\s*')

_help_end_re = re.compile(r"""(%{0,2}
                              [a-zA-Z_*][\w*]*        # Variable name
                              (\.[a-zA-Z_*][\w*]*)*   # .etc.etc
                              )
                              (\?\??)$                # ? or ??""",
                              re.VERBOSE)

def has_comment(src):
    """Indicate whether an input line has (i.e. ends in, or is) a comment.

    This uses tokenize, so it can distinguish comments from # inside strings.

    Parameters
    ----------
    src : string
      A single line input string.

    Returns
    -------
    Boolean: True if source has a comment.
    """
    readline = StringIO(src).readline
    toktypes = set()
    try:
        for t in tokenize.generate_tokens(readline):
            toktypes.add(t[0])
    except tokenize.TokenError:
        pass
    return(tokenize.COMMENT in toktypes)


@StatelessInputTransformer.wrap
def help_end(line):
    """Translate lines with ?/?? at the end"""
    m = _help_end_re.search(line)
    if m is None or has_comment(line):
        return line
    target = m.group(1)
    esc = m.group(3)
    lspace = _initial_space_re.match(line).group(0)

    # If we're mid-command, put it back on the next prompt for the user.
    next_input = line.rstrip('?') if line.strip() != m.group(0) else None

    return _make_help_call(target, esc, lspace, next_input)


@CoroutineInputTransformer.wrap
def cellmagic():
    """Captures & transforms cell magics.
    
    After a cell magic is started, this stores up any lines it gets until it is
    reset (sent None).
    """
    tpl = 'get_ipython().run_cell_magic(%r, %r, %r)'
    cellmagic_help_re = re.compile('%%\w+\?')
    line = ''
    while True:
        line = (yield line)
        if (not line) or (not line.startswith(ESC_MAGIC2)):
            continue
        
        if cellmagic_help_re.match(line):
            # This case will be handled by help_end
            continue
        
        first = line
        body = []
        line = (yield None)
        while (line is not None) and (line.strip() != ''):
            body.append(line)
            line = (yield None)
        
        # Output
        magic_name, _, first = first.partition(' ')
        magic_name = magic_name.lstrip(ESC_MAGIC2)
        line = tpl % (magic_name, first, u'\n'.join(body))


def _strip_prompts(prompt1_re, prompt2_re):
    """Remove matching input prompts from a block of input."""
    line = ''
    while True:
        line = (yield line)
        
        if line is None:
            continue
        
        m = prompt1_re.match(line)
        if m:
            while m:
                line = (yield line[len(m.group(0)):])
                if line is None:
                    break
                m = prompt2_re.match(line)
        else:
            # Prompts not in input - wait for reset
            while line is not None:
                line = (yield line)

@CoroutineInputTransformer.wrap
def classic_prompt():
    """Strip the >>>/... prompts of the Python interactive shell."""
    prompt1_re = re.compile(r'^(>>> )')
    prompt2_re = re.compile(r'^(>>> |^\.\.\. )')
    return _strip_prompts(prompt1_re, prompt2_re)

classic_prompt.look_in_string = True

@CoroutineInputTransformer.wrap
def ipy_prompt():
    """Strip IPython's In [1]:/...: prompts."""
    prompt1_re = re.compile(r'^In \[\d+\]: ')
    prompt2_re = re.compile(r'^(In \[\d+\]: |^\ \ \ \.\.\.+: )')
    return _strip_prompts(prompt1_re, prompt2_re)

ipy_prompt.look_in_string = True


@CoroutineInputTransformer.wrap
def leading_indent():
    """Remove leading indentation.
    
    If the first line starts with a spaces or tabs, the same whitespace will be
    removed from each following line until it is reset.
    """
    space_re = re.compile(r'^[ \t]+')
    line = ''
    while True:
        line = (yield line)
        
        if line is None:
            continue
        
        m = space_re.match(line)
        if m:
            space = m.group(0)
            while line is not None:
                if line.startswith(space):
                    line = line[len(space):]
                line = (yield line)
        else:
            # No leading spaces - wait for reset
            while line is not None:
                line = (yield line)

leading_indent.look_in_string = True


def _special_assignment(assignment_re, template):
    """Transform assignment from system & magic commands.
    
    This is stateful so that it can handle magic commands continued on several
    lines.
    """
    line = ''
    while True:
        line = (yield line)
        if not line or line.isspace():
            continue
        
        m = assignment_re.match(line)
        if not m:
            continue
        
        parts = []
        while line is not None:
            parts.append(line.rstrip('\\'))
            if not line.endswith('\\'):
                break
            line = (yield None)
        
        # Output
        whole = assignment_re.match(' '.join(parts))
        line = template % (whole.group('lhs'), whole.group('cmd'))

@CoroutineInputTransformer.wrap
def assign_from_system():
    """Transform assignment from system commands (e.g. files = !ls)"""
    assignment_re = re.compile(r'(?P<lhs>(\s*)([\w\.]+)((\s*,\s*[\w\.]+)*))'
                               r'\s*=\s*!\s*(?P<cmd>.*)')
    template = '%s = get_ipython().getoutput(%r)'
    return _special_assignment(assignment_re, template)

@CoroutineInputTransformer.wrap
def assign_from_magic():
    """Transform assignment from magic commands (e.g. a = %who_ls)"""
    assignment_re = re.compile(r'(?P<lhs>(\s*)([\w\.]+)((\s*,\s*[\w\.]+)*))'
                               r'\s*=\s*%\s*(?P<cmd>.*)')
    template = '%s = get_ipython().magic(%r)'
    return _special_assignment(assignment_re, template)
