
//============================================================================
// Kernel
//============================================================================

var IPython = (function (IPython) {

    var utils = IPython.utils;

    var Kernel = function () {
        this.kernel_id = null;
        this.base_url = "/kernels";
        this.kernel_url = null;
    };


    Kernel.prototype.get_msg = function (msg_type, content) {
        var msg = {
            header : {
                msg_id : utils.uuid(),
                username : "bgranger",
                session: this.session_id,
                msg_type : msg_type
            },
            content : content,
            parent_header : {}
        };
        return msg;
    }

    Kernel.prototype.start_kernel = function (callback) {
        var that = this;
        $.post(this.base_url,
            function (kernel_id) {
                that._handle_start_kernel(kernel_id, callback);
            }, 
            'json'
        );
    };


    Kernel.prototype._handle_start_kernel = function (kernel_id, callback) {
        this.kernel_id = kernel_id;
        this.kernel_url = this.base_url + "/" + this.kernel_id;
        this._start_channels();
        callback();
    };


    Kernel.prototype._start_channels = function () {
        var ws_url = "ws://127.0.0.1:8888" + this.kernel_url;
        this.shell_channel = new WebSocket(ws_url + "/shell");
        this.iopub_channel = new WebSocket(ws_url + "/iopub");
    }


    Kernel.prototype.execute = function (code) {
        var content = {
            code : code,
            silent : false,
            user_variables : [],
            user_expressions : {}
        };
        var msg = this.get_msg("execute_request", content);
        this.shell_channel.send(JSON.stringify(msg));
        return msg.header.msg_id;
    }


    Kernel.prototype.interrupt = function () {
        $.post(this.kernel_url + "/interrupt");
    };


    Kernel.prototype.restart = function () {
        IPython.kernel_status_widget.status_restarting();
        url = this.kernel_url + "/restart"
        var that = this;
        $.post(url, function (kernel_id) {
            console.log("Kernel restarted: " + kernel_id);
            that.kernel_id = kernel_id;
            that.kernel_url = that.base_url + "/" + that.kernel_id;
            IPython.kernel_status_widget.status_idle();
        }, 'json');
    };


    IPython.Kernel = Kernel;

    return IPython;

}(IPython));

