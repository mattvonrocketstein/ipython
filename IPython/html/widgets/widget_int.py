"""IntWidget class.  

Represents an unbounded int using a widget.
"""
#-----------------------------------------------------------------------------
# Copyright (c) 2013, the IPython Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
from .widget import DOMWidget
from IPython.utils.traitlets import Unicode, Int, Bool, List

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------
class IntWidget(DOMWidget):
    target_name = Unicode('IntWidgetModel')
    view_name = Unicode('IntTextView')

    # Keys
    keys = ['value', 'disabled', 'description'] + DOMWidget.keys
    value = Int(0, help="Int value") 
    disabled = Bool(False, help="Enable or disable user changes")
    description = Unicode(help="Description of the value this widget represents")
