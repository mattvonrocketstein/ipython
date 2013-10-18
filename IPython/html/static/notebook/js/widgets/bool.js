
require(["notebook/js/widget"], function(){
    
    var BoolWidgetModel = IPython.WidgetModel.extend({});
    IPython.notebook.widget_manager.register_widget_model('BoolWidgetModel', BoolWidgetModel);

    var CheckboxView = IPython.WidgetView.extend({
      
        // Called when view is rendered.
        render : function(){
            this.$el
                .html('')
                .addClass(this.model.comm.comm_id);

            var $label = $('<label />')
                .addClass('checkbox')
                .appendTo(this.$el);
            this.$checkbox = $('<input />')
                .attr('type', 'checkbox')
                .appendTo($label);
            this.$checkbox_label = $('<div />')
                .appendTo($label);

            this.update(); // Set defaults.
        },
        
        // Handles: Backend -> Frontend Sync
        //          Frontent -> Frontend Sync
        update : function(){
            if (!this.user_invoked_update) {
                this.$checkbox.prop('checked', this.model.get('value'));
                this.$checkbox_label.html(this.model.get('description'));
            }
        },
        
        events: {"change input" : "handleChanged"},
        
        // Handles and validates user input.
        handleChanged: function(e) { 
            this.user_invoked_update = true;
            this.model.set('value', $(e.target).prop('checked'));
            this.model.apply(this);
            this.user_invoked_update = false;
        },
    });

    IPython.notebook.widget_manager.register_widget_view('CheckboxView', CheckboxView);
});
