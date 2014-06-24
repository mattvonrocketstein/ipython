// Copyright (c) IPython Development Team.
// Distributed under the terms of the Modified BSD License.

require([
    'base/js/namespace',
    'jquery',
    'notebook/js/notebook',
    'base/js/utils',
    'base/js/page',
    'notebook/js/layoutmanager',
    'base/js/events',
    'auth/js/loginwidget',
    'notebook/js/maintoolbar',
    'notebook/js/pager',
    'notebook/js/quickhelp',
    'notebook/js/menubar',
    'notebook/js/notificationarea',
    'notebook/js/savewidget',
    'notebook/js/keyboardmanager',
    'notebook/js/config',
], function(
    IPython, 
    $,
    notebook, 
    utils, 
    page, 
    layoutmanager, 
    events,
    loginwidget, 
    maintoolbar, 
    pager, 
    quickhelp, 
    menubar, 
    notificationarea, 
    savewidget, 
    keyboardmanager,
    config
    ) {
    "use strict";

    $('#ipython-main-app').addClass('border-box-sizing');
    $('div#notebook_panel').addClass('border-box-sizing');

    var options = {
        base_url : utils.get_body_data("baseUrl"),
        notebook_path : utils.get_body_data("notebookPath"),
        notebook_name : utils.get_body_data('notebookName')
    };

    var user_config = $.extend({}, config.default_config);
    options.user_config = user_config;
    var page = new page.Page();
    var layout_manager = new layoutmanager.LayoutManager();
    options.layout_manager = layout_manager;
    var events = $([new events.Events()]);
    options.events = events;
    var pager = new pager.Pager('div#pager', 'div#pager_splitter', layout_manager, events);
    var keyboard_manager = new keyboardmanager.KeyboardManager(pager, events);
    options.keyboard_manager = keyboard_manager;
    var save_widget = new savewidget.SaveWidget('span#save_widget', events);
    options.save_widget = save_widget;
    var notebook = new notebook.Notebook('div#notebook', options); 
    options.notebook = notebook;
    var login_widget = new loginwidget.LoginWidget('span#login_widget', options);
    var toolbar = new maintoolbar.MainToolBar('#maintoolbar-container', options); 
    var quick_help = new quickhelp.QuickHelp(undefined, options); 
    options.quick_help = quick_help;
    var menubar = new menubar.MenuBar('#menubar', options);
    var notification_area = new notificationarea.NotificationArea('#notification_area', options);
    notification_area.init_notification_widgets();

    $('body').append('<div id="fonttest"><pre><span id="test1">x</span>'+
                     '<span id="test2" style="font-weight: bold;">x</span>'+
                     '<span id="test3" style="font-style: italic;">x</span></pre></div>');
    var nh = $('#test1').innerHeight();
    var bh = $('#test2').innerHeight();
    var ih = $('#test3').innerHeight();
    if(nh != bh || nh != ih) {
        $('head').append('<style>.CodeMirror span { vertical-align: bottom; }</style>');
    }
    $('#fonttest').remove();

    page.show();

    layout_manager.do_resize();
    var first_load = function () {
        layout_manager.do_resize();
        var hash = document.location.hash;
        if (hash) {
            document.location.hash = '';
            document.location.hash = hash;
        }
        notebook.set_autosave_interval(notebook.minimum_autosave_interval);
        // only do this once
        events.off('notebook_loaded.Notebook', first_load);
    };
    
    events.on('notebook_loaded.Notebook', first_load);
    events.trigger('app_initialized.NotebookApp');
    notebook.load_notebook(options.notebook_name, options.notebook_path);

    IPython.page = page;
    IPython.layout_manager = layout_manager;
    IPython.notebook = notebook;
    IPython.pager = pager;
    IPython.quick_help = quick_help;
    IPython.login_widget = login_widget;
    IPython.menubar = menubar;
    IPython.toolbar = toolbar;
    IPython.notification_area = notification_area;
    IPython.events = events;
    IPython.keyboard_manager = keyboard_manager;
    IPython.save_widget = save_widget;
    IPython.config = user_config;
});
