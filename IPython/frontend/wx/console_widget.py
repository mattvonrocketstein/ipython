# encoding: utf-8
"""
A Wx widget to act as a console and input commands.

This widget deals with prompts and provides an edit buffer
restricted to after the last prompt.
"""

__docformat__ = "restructuredtext en"

#-------------------------------------------------------------------------------
#  Copyright (C) 2008  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is
#  in the file COPYING, distributed as part of this software.
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Imports
#-------------------------------------------------------------------------------

import wx
import wx.stc  as  stc

from wx.py import editwindow
import time
import sys
import string

LINESEP = '\n'
if sys.platform == 'win32':
    LINESEP = '\n\r'

import re

# FIXME: Need to provide an API for non user-generated display on the
# screen: this should not be editable by the user.
#-------------------------------------------------------------------------------
# Constants 
#-------------------------------------------------------------------------------
_COMPLETE_BUFFER_MARKER = 31
_ERROR_MARKER = 30
_INPUT_MARKER = 29

_DEFAULT_SIZE = 10
if sys.platform == 'darwin':
    _DEFAULT_SIZE = 12

_DEFAULT_STYLE = {
    #background definition
    'default'     : 'size:%d' % _DEFAULT_SIZE,
    'bracegood'   : 'fore:#00AA00,back:#000000,bold',
    'bracebad'    : 'fore:#FF0000,back:#000000,bold',

    # Edge column: a number of None
    'edge_column' : -1,

    # properties for the various Python lexer styles
    'comment'       : 'fore:#007F00',
    'number'        : 'fore:#007F7F',
    'string'        : 'fore:#7F007F,italic',
    'char'          : 'fore:#7F007F,italic',
    'keyword'       : 'fore:#00007F,bold',
    'triple'        : 'fore:#7F0000',
    'tripledouble'  : 'fore:#7F0000',
    'class'         : 'fore:#0000FF,bold,underline',
    'def'           : 'fore:#007F7F,bold',
    'operator'      : 'bold'
    }

# new style numbers
_STDOUT_STYLE = 15
_STDERR_STYLE = 16
_TRACE_STYLE  = 17


# system colors
#SYS_COLOUR_BACKGROUND = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BACKGROUND)

# Translation table from ANSI escape sequences to color. 
ANSI_STYLES = {'0;30': [0, 'BLACK'],            '0;31': [1, 'RED'],
               '0;32': [2, 'GREEN'],           '0;33': [3, 'BROWN'],
               '0;34': [4, 'BLUE'],            '0;35': [5, 'PURPLE'],
               '0;36': [6, 'CYAN'],            '0;37': [7, 'LIGHT GREY'],
               '1;30': [8, 'DARK GREY'],       '1;31': [9, 'RED'],
               '1;32': [10, 'SEA GREEN'],      '1;33': [11, 'YELLOW'],
               '1;34': [12, 'LIGHT BLUE'],     '1;35': 
                                                 [13, 'MEDIUM VIOLET RED'],
               '1;36': [14, 'LIGHT STEEL BLUE'], '1;37': [15, 'YELLOW']}

#we define platform specific fonts
if wx.Platform == '__WXMSW__':
    FACES = { 'times': 'Times New Roman',
                'mono' : 'Courier New',
                'helv' : 'Arial',
                'other': 'Comic Sans MS',
                'size' : 10,
                'size2': 8,
                }
elif wx.Platform == '__WXMAC__':
    FACES = { 'times': 'Times New Roman',
                'mono' : 'Monaco',
                'helv' : 'Arial',
                'other': 'Comic Sans MS',
                'size' : 10,
                'size2': 8,
                }
else:
    FACES = { 'times': 'Times',
                'mono' : 'Courier',
                'helv' : 'Helvetica',
                'other': 'new century schoolbook',
                'size' : 10,
                'size2': 8,
                }
 

#-------------------------------------------------------------------------------
# The console widget class
#-------------------------------------------------------------------------------
class ConsoleWidget(editwindow.EditWindow):
    """ Specialized styled text control view for console-like workflow.

        This widget is mainly interested in dealing with the prompt and
        keeping the cursor inside the editing line.
    """

    # This is where the title captured from the ANSI escape sequences are
    # stored.
    title = 'Console'

    # Last prompt printed
    last_prompt = ''

    # The buffer being edited.
    def _set_input_buffer(self, string):
        self.SetSelection(self.current_prompt_pos, self.GetLength())
        self.ReplaceSelection(string)
        self.GotoPos(self.GetLength())

    def _get_input_buffer(self):
        """ Returns the text in current edit buffer.
        """
        input_buffer = self.GetTextRange(self.current_prompt_pos,
                                                self.GetLength())
        input_buffer = input_buffer.replace(LINESEP, '\n')
        return input_buffer

    input_buffer = property(_get_input_buffer, _set_input_buffer)

    style = _DEFAULT_STYLE.copy()

    # Translation table from ANSI escape sequences to color. Override
    # this to specify your colors.
    ANSI_STYLES = ANSI_STYLES.copy()
    
    # Font faces
    faces = FACES.copy()
                 
    # Store the last time a refresh was done
    _last_refresh_time = 0

    #--------------------------------------------------------------------------
    # Public API
    #--------------------------------------------------------------------------
    
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, 
                        size=wx.DefaultSize, style=wx.WANTS_CHARS, ):
        editwindow.EditWindow.__init__(self, parent, id, pos, size, style)
        self.configure_scintilla()
        # Track if 'enter' key as ever been processed
        # This variable will only be reallowed until key goes up
        self.enter_catched = False 
        self.current_prompt_pos = 0

        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self.Bind(wx.EVT_KEY_UP, self._on_key_up)
    

    def write(self, text, refresh=True):
        """ Write given text to buffer, while translating the ansi escape
            sequences.
        """
        # XXX: do not put print statements to sys.stdout/sys.stderr in 
        # this method, the print statements will call this method, as 
        # you will end up with an infinit loop
        title = self.title_pat.split(text)
        if len(title)>1:
            self.title = title[-2]

        text = self.title_pat.sub('', text)
        segments = self.color_pat.split(text)
        segment = segments.pop(0)
        self.GotoPos(self.GetLength())
        self.StartStyling(self.GetLength(), 0xFF)
        try:
            self.AppendText(segment)
        except UnicodeDecodeError:
            # XXX: Do I really want to skip the exception?
            pass
        
        if segments:
            for ansi_tag, text in zip(segments[::2], segments[1::2]):
                self.StartStyling(self.GetLength(), 0xFF)
                try:
                    self.AppendText(text)
                except UnicodeDecodeError:
                    # XXX: Do I really want to skip the exception?
                    pass

                if ansi_tag not in self.ANSI_STYLES:
                    style = 0
                else:
                    style = self.ANSI_STYLES[ansi_tag][0]

                self.SetStyling(len(text), style) 
                
        self.GotoPos(self.GetLength())
        if refresh:
            current_time = time.time()
            if current_time - self._last_refresh_time > 0.03:
                if sys.platform == 'win32':
                    wx.SafeYield()
                else:
                    wx.Yield()
                #    self.ProcessEvent(wx.PaintEvent())
                self._last_refresh_time = current_time 

   
    def new_prompt(self, prompt):
        """ Prints a prompt at start of line, and move the start of the
            current block there.

            The prompt can be given with ascii escape sequences.
        """
        self.write(prompt, refresh=False)
        # now we update our cursor giving end of prompt
        self.current_prompt_pos = self.GetLength()
        self.current_prompt_line = self.GetCurrentLine()
        self.EnsureCaretVisible()
        self.last_prompt = prompt


    def continuation_prompt(self):
        """Returns the current continuation prompt.
        """
        # ASCII-less prompt
        ascii_less = ''.join(self.color_pat.split(self.last_prompt)[2::2])
        return "."*(len(ascii_less)-2) + ': '
 

    def scroll_to_bottom(self):
        maxrange = self.GetScrollRange(wx.VERTICAL)
        self.ScrollLines(maxrange)


    def pop_completion(self, possibilities, offset=0):
        """ Pops up an autocompletion menu. Offset is the offset
            in characters of the position at which the menu should
            appear, relativ to the cursor.
        """
        self.AutoCompSetIgnoreCase(False)
        self.AutoCompSetAutoHide(False)
        self.AutoCompSetMaxHeight(len(possibilities))
        self.AutoCompShow(offset, " ".join(possibilities))


    def get_line_width(self):
        """ Return the width of the line in characters.
        """
        return self.GetSize()[0]/self.GetCharWidth()



    #--------------------------------------------------------------------------
    # EditWindow API
    #--------------------------------------------------------------------------

    def OnUpdateUI(self, event):
        """ Override the OnUpdateUI of the EditWindow class, to prevent 
            syntax highlighting both for faster redraw, and for more
            consistent look and feel.
        """

    #--------------------------------------------------------------------------
    # Styling API
    #--------------------------------------------------------------------------

    def configure_scintilla(self):

        p = self.style
        
        #First we define the special background colors        
        if 'trace' in p:
            _COMPLETE_BUFFER_BG = p['trace']
        else:
            _COMPLETE_BUFFER_BG = '#FAFAF1' # Nice green

        if 'stdout' in p:
            _INPUT_BUFFER_BG = p['stdout']
        else:
            _INPUT_BUFFER_BG = '#FDFFD3' # Nice yellow

        if 'stderr' in p:
            _ERROR_BG = p['stderr']
        else:
            _ERROR_BG = '#FFF1F1' # Nice red

        # Marker for complete buffer.
        self.MarkerDefine(_COMPLETE_BUFFER_MARKER, stc.STC_MARK_BACKGROUND,
                                background = _COMPLETE_BUFFER_BG)

        # Marker for current input buffer.
        self.MarkerDefine(_INPUT_MARKER, stc.STC_MARK_BACKGROUND,
                                background = _INPUT_BUFFER_BG)
        # Marker for tracebacks.
        self.MarkerDefine(_ERROR_MARKER, stc.STC_MARK_BACKGROUND,
                                background = _ERROR_BG)

        self.SetEOLMode(stc.STC_EOL_LF)

        # Ctrl"+" or Ctrl "-" can be used to zoomin/zoomout the text inside 
        # the widget
        self.CmdKeyAssign(ord('+'), stc.STC_SCMOD_CTRL, stc.STC_CMD_ZOOMIN)
        self.CmdKeyAssign(ord('-'), stc.STC_SCMOD_CTRL, stc.STC_CMD_ZOOMOUT)
        # Also allow Ctrl Shift "=" for poor non US keyboard users. 
        self.CmdKeyAssign(ord('='), stc.STC_SCMOD_CTRL|stc.STC_SCMOD_SHIFT, 
                                            stc.STC_CMD_ZOOMIN)
        
        # Keys: we need to clear some of the keys the that don't play
        # well with a console.
        self.CmdKeyClear(ord('D'), stc.STC_SCMOD_CTRL)
        self.CmdKeyClear(ord('L'), stc.STC_SCMOD_CTRL)
        self.CmdKeyClear(ord('T'), stc.STC_SCMOD_CTRL)
        self.CmdKeyClear(ord('A'), stc.STC_SCMOD_CTRL)

        self.SetEOLMode(stc.STC_EOL_CRLF)
        self.SetWrapMode(stc.STC_WRAP_CHAR)
        self.SetWrapMode(stc.STC_WRAP_WORD)
        self.SetBufferedDraw(True)

        if 'antialiasing' in p:
            self.SetUseAntiAliasing(p['antialiasing'])            
        else:        
            self.SetUseAntiAliasing(True)

        self.SetLayoutCache(stc.STC_CACHE_PAGE)
        self.SetUndoCollection(False)
        self.SetUseTabs(True)
        self.SetIndent(4)
        self.SetTabWidth(4)

        # we don't want scintilla's autocompletion to choose 
        # automaticaly out of a single choice list, as we pop it up
        # automaticaly
        self.AutoCompSetChooseSingle(False)
        self.AutoCompSetMaxHeight(10)
        # XXX: this doesn't seem to have an effect.
        self.AutoCompSetFillUps('\n')

        self.SetMargins(3, 3) #text is moved away from border with 3px
        # Suppressing Scintilla margins
        self.SetMarginWidth(0, 0)
        self.SetMarginWidth(1, 0)
        self.SetMarginWidth(2, 0)

        # Xterm escape sequences
        self.color_pat = re.compile('\x01?\x1b\[(.*?)m\x02?')
        self.title_pat = re.compile('\x1b]0;(.*?)\x07')

        # styles
        
        if 'carret_color' in p:
            self.SetCaretForeground(p['carret_color'])
        else:
            self.SetCaretForeground('BLACK')
        
        if 'background_color' in p:
            background_color = p['background_color']
        else:
            background_color = 'WHITE'            
            
        if 'default' in p:
            if 'back' not in p['default']:
                p['default'] += ',back:%s' % background_color
            if 'size' not in p['default']:
                p['default'] += ',size:%s' % self.faces['size']
            if 'face' not in p['default']:
                p['default'] += ',face:%s' % self.faces['mono']
            
            self.StyleSetSpec(stc.STC_STYLE_DEFAULT, p['default'])
        else:
            self.StyleSetSpec(stc.STC_STYLE_DEFAULT, 
                            "fore:%s,back:%s,size:%d,face:%s" 
                            % (self.ANSI_STYLES['0;30'][1], 
                               background_color,
                               self.faces['size'], self.faces['mono']))
        
        #all styles = default one        
        self.StyleClearAll()
        
        # XXX: two lines below are usefull if not using the lexer        
        #for style in self.ANSI_STYLES.values():
        #    self.StyleSetSpec(style[0], "bold,fore:%s" % style[1])        

        #prompt definition
        if 'prompt_in1' in p:
            self.prompt_in1 = p['prompt_in1']
        else:
            self.prompt_in1 = \
            '\n\x01\x1b[0;34m\x02In [\x01\x1b[1;34m\x02$number\x01\x1b[0;34m\x02]: \x01\x1b[0m\x02'

        if 'prompt_out' in p:
            self.prompt_out = p['prompt_out']
        else:
            self.prompt_out = \
            '\x01\x1b[0;31m\x02Out[\x01\x1b[1;31m\x02$number\x01\x1b[0;31m\x02]: \x01\x1b[0m\x02'

        self.output_prompt_template = string.Template(self.prompt_out)
        self.input_prompt_template = string.Template(self.prompt_in1)

        if 'stdout' in p:
            self.StyleSetSpec(_STDOUT_STYLE, p['stdout'])
        if 'stderr' in p:
            self.StyleSetSpec(_STDERR_STYLE, p['stderr'])
        if 'trace' in p:
            self.StyleSetSpec(_TRACE_STYLE, p['trace'])
        if 'bracegood' in p:
            self.StyleSetSpec(stc.STC_STYLE_BRACELIGHT, p['bracegood'])
        if 'bracebad' in p:
            self.StyleSetSpec(stc.STC_STYLE_BRACEBAD, p['bracebad'])
        if 'comment' in p:
            self.StyleSetSpec(stc.STC_P_COMMENTLINE, p['comment'])
        if 'number' in p:
            self.StyleSetSpec(stc.STC_P_NUMBER, p['number'])
        if 'string' in p:
            self.StyleSetSpec(stc.STC_P_STRING, p['string'])
        if 'char' in p:
            self.StyleSetSpec(stc.STC_P_CHARACTER, p['char'])
        if 'keyword' in p:
            self.StyleSetSpec(stc.STC_P_WORD, p['keyword'])
        if 'keyword' in p:
            self.StyleSetSpec(stc.STC_P_WORD2, p['keyword'])
        if 'triple' in p:
            self.StyleSetSpec(stc.STC_P_TRIPLE, p['triple'])
        if 'tripledouble' in p:
            self.StyleSetSpec(stc.STC_P_TRIPLEDOUBLE, p['tripledouble'])
        if 'class' in p:
            self.StyleSetSpec(stc.STC_P_CLASSNAME, p['class'])
        if 'def' in p:
            self.StyleSetSpec(stc.STC_P_DEFNAME, p['def'])
        if 'operator' in p:
            self.StyleSetSpec(stc.STC_P_OPERATOR, p['operator'])
        if 'comment' in p:
            self.StyleSetSpec(stc.STC_P_COMMENTBLOCK, p['comment'])

        if 'edge_column' in p:
            edge_column = p['edge_column']
            if edge_column is not None and edge_column > 0:
                #we add a vertical line to console widget
                self.SetEdgeMode(stc.STC_EDGE_LINE)
                self.SetEdgeColumn(88)
 
        
    #--------------------------------------------------------------------------
    # Private API
    #--------------------------------------------------------------------------
   
    def _on_key_down(self, event, skip=True):
        """ Key press callback used for correcting behavior for 
            console-like interfaces: the cursor is constraint to be after
            the last prompt.

            Return True if event as been catched.
        """
        catched = True
        # Intercept some specific keys.
        if event.KeyCode == ord('L') and event.ControlDown() :
            self.scroll_to_bottom()
        elif event.KeyCode == ord('K') and event.ControlDown() :
            self.input_buffer = ''
        elif event.KeyCode == ord('A') and event.ControlDown() :
            self.GotoPos(self.GetLength())
            self.SetSelectionStart(self.current_prompt_pos)
            self.SetSelectionEnd(self.GetCurrentPos())
            catched = True
        elif event.KeyCode == ord('E') and event.ControlDown() :
            self.GotoPos(self.GetLength())
            catched = True
        elif event.KeyCode == wx.WXK_PAGEUP:
            self.ScrollPages(-1)
        elif event.KeyCode == wx.WXK_PAGEDOWN:
            self.ScrollPages(1)
        elif event.KeyCode == wx.WXK_UP and event.ShiftDown():
            self.ScrollLines(-1)
        elif event.KeyCode == wx.WXK_DOWN and event.ShiftDown():
            self.ScrollLines(1)
        else:
            catched = False

        if self.AutoCompActive():
            event.Skip()
        else:
            if event.KeyCode in (13, wx.WXK_NUMPAD_ENTER) and \
                        event.Modifiers in (wx.MOD_NONE, wx.MOD_WIN):
                catched = True
                if not self.enter_catched:
                    self.CallTipCancel()
                    self.write('\n', refresh=False)
                    # Under windows scintilla seems to be doing funny
                    # stuff to the line returns here, but the getter for
                    # input_buffer filters this out.
                    if sys.platform == 'win32':
                        self.input_buffer = self.input_buffer
                    self._on_enter()
                    self.enter_catched = True

            elif event.KeyCode == wx.WXK_HOME:
                if event.Modifiers in (wx.MOD_NONE, wx.MOD_WIN):
                    self.GotoPos(self.current_prompt_pos)
                    catched = True

                elif event.Modifiers == wx.MOD_SHIFT:
                    # FIXME: This behavior is not ideal: if the selection
                    # is already started, it will jump.
                    self.SetSelectionStart(self.current_prompt_pos) 
                    self.SetSelectionEnd(self.GetCurrentPos())
                    catched = True

            elif event.KeyCode == wx.WXK_UP:
                if self.GetCurrentLine() > self.current_prompt_line:
                    if self.GetCurrentLine() == self.current_prompt_line + 1 \
                            and self.GetColumn(self.GetCurrentPos()) < \
                                self.GetColumn(self.current_prompt_pos):
                        self.GotoPos(self.current_prompt_pos)
                    else:
                        event.Skip()
                catched = True

            elif event.KeyCode in (wx.WXK_LEFT, wx.WXK_BACK):
                if not self._keep_cursor_in_buffer(self.GetCurrentPos() - 1):
                    event.Skip()
                catched = True

            elif event.KeyCode == wx.WXK_RIGHT:
                if not self._keep_cursor_in_buffer(self.GetCurrentPos() + 1):
                    event.Skip()
                catched = True


            elif event.KeyCode == wx.WXK_DELETE:
                if not self._keep_cursor_in_buffer(self.GetCurrentPos() - 1):
                    event.Skip()
                catched = True

            if skip and not catched:
                # Put the cursor back in the edit region
                if not self._keep_cursor_in_buffer():
                    if not (self.GetCurrentPos() == self.GetLength()
                                and event.KeyCode == wx.WXK_DELETE):
                        event.Skip()
                    catched = True

        return catched


    def _on_key_up(self, event, skip=True):
        """ If cursor is outside the editing region, put it back.
        """
        if skip:
            event.Skip()
        self._keep_cursor_in_buffer()


    def _keep_cursor_in_buffer(self, pos=None):
        """ Checks if the cursor is where it is allowed to be. If not,
            put it back.

            Returns
            -------
            cursor_moved: Boolean
                whether or not the cursor was moved by this routine.

            Notes
            ------
                WARNING: This does proper checks only for horizontal
                movements.
        """
        if pos is None:
            current_pos = self.GetCurrentPos()
        else:
            current_pos = pos
        if  current_pos < self.current_prompt_pos:
            self.GotoPos(self.current_prompt_pos)
            return True
        line_num = self.LineFromPosition(current_pos)
        if not current_pos > self.GetLength():
            line_pos = self.GetColumn(current_pos)
        else:
            line_pos = self.GetColumn(self.GetLength())
        line = self.GetLine(line_num)
        # Jump the continuation prompt
        continuation_prompt = self.continuation_prompt()
        if ( line.startswith(continuation_prompt)
                     and line_pos < len(continuation_prompt)+1):
            if line_pos < 2:
                # We are at the beginning of the line, trying to move
                # forward: jump forward.
                self.GotoPos(current_pos + 1 +
                                    len(continuation_prompt) - line_pos)
            else:
                # Jump back up
                self.GotoPos(self.GetLineEndPosition(line_num-1))
            return True
        elif ( current_pos > self.GetLineEndPosition(line_num) 
                        and not current_pos == self.GetLength()): 
            # Jump to next line
            self.GotoPos(current_pos + 1 +
                                    len(continuation_prompt))
            return True

        self.enter_catched = False #we re-allow enter event processing
        return False


if __name__ == '__main__':
    # Some simple code to test the console widget.
    class MainWindow(wx.Frame):
        def __init__(self, parent, id, title):
            wx.Frame.__init__(self, parent, id, title, size=(300, 250))
            self._sizer = wx.BoxSizer(wx.VERTICAL)
            self.console_widget = ConsoleWidget(self)
            self._sizer.Add(self.console_widget, 1, wx.EXPAND)
            self.SetSizer(self._sizer)
            self.SetAutoLayout(1)
            self.Show(True)

    app = wx.PySimpleApp()
    w = MainWindow(None, wx.ID_ANY, 'ConsoleWidget')
    w.SetSize((780, 460))
    w.Show()

    app.MainLoop()


