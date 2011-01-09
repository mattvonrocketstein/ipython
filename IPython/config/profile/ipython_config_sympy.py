c = get_config()

# This can be used at any point in a config file to load a sub config
# and merge it into the current one.
load_subconfig('ipython_config.py')

lines = """
from __future__ import division
from sympy import *
x, y, z = symbols('xyz')
k, m, n = symbols('kmn', integer=True)
f, g, h = map(Function, 'fgh')
"""

# You have to make sure that attributes that are containers already
# exist before using them.  Simple assigning a new list will override
# all previous values.

if hasattr(c.Global, 'exec_lines'):
    c.Global.exec_lines.append(lines)
else:
    c.Global.exec_lines = [lines]

if hasattr(c.Global, 'extensions'):
    c.Global.extensions.append('IPython.extensions.sympy_printing')
else:
    c.Global.extensions = ['IPython.extensions.sympy_printing']

