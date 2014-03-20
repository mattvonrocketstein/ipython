// Test the notebook dual mode feature.

// Test
casper.notebook_test(function () {
    var index = this.append_cell('print("a")');
    this.execute_cell_then(index);
    index = this.append_cell('print("b")');
    this.execute_cell_then(index);
    index = this.append_cell('print("c")');
    this.execute_cell_then(index);

    this.then(function () {
        this.validate_state('initial state', 'edit', 0);
        this.key_press('esc');
        this.validate_state('esc', 'command', 0);
        this.key_press('down');
        this.validate_state('down', 'command', 1);
        this.key_press('enter');
        this.validate_state('enter', 'edit', 1);
        this.key_press('j');
        this.validate_state('j in edit mode', 'edit', 1);
        this.key_press('esc');
        this.validate_state('esc', 'command', 1);
        this.key_press('j');
        this.validate_state('j in command mode', 'command', 2);
        this.click_cell(0);
        this.validate_state('click cell 0', 'edit', 0);
        this.click_cell(3);
        this.validate_state('click cell 3', 'edit', 3);
        this.key_press('esc');
        this.validate_state('esc', 'command', 3);

        // Open keyboard help
        this.evaluate(function(){
            $('#keyboard_shortcuts a').click();
        }, {});

        this.key_press('k');
        this.validate_state('k in command mode while keyboard help is up', 'command', 3);

        // Close keyboard help
        this.evaluate(function(){
            $('div.modal button.close').click();
        }, {});

        this.key_press('k');
        this.validate_state('k in command mode', 'command', 2);
        this.click_cell(0);
        this.validate_state('click cell 0', 'edit', 0);
        this.focus_notebook();
        this.validate_state('focus #notebook', 'command', 0);
        this.click_cell(0);
        this.validate_state('click cell 0', 'edit', 0);
        this.focus_notebook();
        this.validate_state('focus #notebook', 'command', 0);
        this.click_cell(3);
        this.validate_state('click cell 3', 'edit', 3);
        this.key_press('shift+enter');
        this.validate_state('shift+enter (no cell below)', 'edit', 4);
        this.click_cell(3);
        this.validate_state('click cell 3', 'edit', 3);
        this.key_press('shift+enter');
        this.validate_state('shift+enter (cell exists below)', 'command', 4);
        this.click_cell(3);
        this.validate_state('click cell 3', 'edit', 3);
        this.key_press('alt+enter');
        this.validate_state('alt+enter', 'edit', 4);
        this.key_press('ctrl+enter');
        this.validate_state('ctrl+enter', 'command', 4);
    });


    // Utility functions.
    this.validate_state = function(message, mode, cell_index) {
        // General tests.
        this.test.assertEquals(this._get_keyboard_mode(), this._get_notebook_mode(),
            message + '; keyboard and notebook modes match');
        // Is codemirror focused appropriately?
        this.test.assert(this.is_editor_focus_valid(), message + '; cell editor focused appropriately');
        // Is the selected cell the only cell that is selected?
        if (cell_index!==undefined) {
            this.test.assert(this.is_cell_selected(cell_index),
                message + '; cell ' + cell_index + ' is the only cell selected');
        }

        // Mode specific tests.
        if (mode==='command') {
            // Are the notebook and keyboard manager in command mode?
            this.test.assertEquals(this._get_keyboard_mode(), 'command',
                message + '; in command mode');
            // Make sure there isn't a single cell in edit mode.
            this.test.assert(this.is_cell_edit(null),
                message + '; all cells in command mode');

        } else if (mode==='edit') {
            // Are the notebook and keyboard manager in edit mode?
            this.test.assertEquals(this._get_keyboard_mode(), 'edit',
                message + '; in edit mode');
            // Is the specified cell the only cell in edit mode?
            if (cell_index!==undefined) {
                this.test.assert(this.is_cell_edit(cell_index),
                    message + '; cell ' + cell_index + ' is the only cell in edit mode');
            }

        } else {
            this.test.assert(false, message + '; ' + mode + ' is an unknown mode');
        }
    };

    this.is_editor_focus_valid = function() {
        var cells = this._get_cells();
        for (var i = 0; i < cells.length; i++) {
            if (!this.is_cell_editor_focus_valid(i)) {
                return false;
            }
        }
        return true;
    };

    this.is_cell_editor_focus_valid = function(i) {
        var cell = this._get_cell(i);
        if (cell) {
            if (cell.mode == 'edit') {
                return this._is_cell_editor_focused(i);
            } else {
                return !this._is_cell_editor_focused(i);
            }
        }
        return true;
    };

    this.is_cell_selected = function(i) {
        return this._is_cell_on(i, 'selected', 'unselected');
    };

    this.is_cell_edit = function(i) {
        return this._is_cell_on(i, 'edit_mode', 'command_mode');
    };

    this.click_cell = function(index) {
        // Code Mirror does not play nicely with emulated brower events.  
        // Instead of trying to emulate a click, here we run code similar to
        // the code used in Code Mirror that handles the mousedown event on a
        // region of codemirror that the user can focus.
        this.evaluate(function (i) {
            cm = IPython.notebook.get_cell(i).code_mirror;
            if (cm.options.readOnly != "nocursor" && (document.activeElement != cm.display.input))
                cm.display.input.focus();
        }, {i: index});
    };

    this.focus_notebook = function() {
        this.evaluate(function (){
            $('#notebook').focus();
        }, {});
    };

    this.key_press = function(key) {
        this.evaluate(function (k) {
            IPython.keyboard.trigger_keydown(k);
        }, {k: key});
    };

    this._is_cell_editor_focused = function(i) {
        return this._is_cell_inputfield(i, '.CodeMirror-focused *');
    };

    this._is_cell_on = function(i, on_class, off_class) {
        var cells = this._get_cells();
        for (var j = 0; j < cells.length; j++) {
            if (j === i) {
                if (this._has_cell_class(j, off_class) || !this._has_cell_class(j, on_class)) {
                    return false;
                }
            } else {
                if (!this._has_cell_class(j, off_class) || this._has_cell_class(j, on_class)) {
                    return false;
                }
            }
        }
        return true;
    };

    this._get_keyboard_mode = function() {
        return this.evaluate(function() {
            return IPython.keyboard_manager.mode;
        }, {});
    };

    this._get_notebook_mode = function() {
        return this.evaluate(function() {
            return IPython.notebook.mode;
        }, {});
    };

    this._get_cells = function() {
        return this.evaluate(function() {
            return IPython.notebook.get_cells();
        }, {});
    };

    this._get_cell = function(index) {
        return this.evaluate(function(i) {
            var cell = IPython.notebook.get_cell(i);
            if (cell) {
                return cell;
            }
            return null;
        }, {i : index});
    };

    this._is_cell_inputfield = function(index, selector) {
        return this.evaluate(function(i, s) {
            var cell = IPython.notebook.get_cell(i);
            if (cell) {
                return $(cell.code_mirror.getInputField()).is(s);
            }
            return false;
        }, {i : index, s: selector});
    };

    this._has_cell_class = function(index, classes) {
        return this.evaluate(function(i, c) {
            var cell = IPython.notebook.get_cell(i);
            if (cell) {
                return cell.element.hasClass(c);
            }
            return false;
        }, {i : index, c: classes});
    };
});
