import json
import logging
import os

import zmq

# Install the pyzmq ioloop. This has to be done before anything else from
# tornado is imported.
from zmq.eventloop import ioloop
import tornado.ioloop
tornado.ioloop = ioloop

from tornado import httpserver
from tornado import options
from tornado import web
from tornado import websocket

from kernelmanager import KernelManager

options.define("port", default=8888, help="run on the given port", type=int)

_session_id_regex = r"(?P<session_id>\w+-\w+-\w+-\w+-\w+)"
_kernel_id_regex = r"(?P<kernel_id>\w+)"


class MainHandler(web.RequestHandler):
    def get(self):
        self.render('notebook.html')


class BaseKernelHandler(object):

    def get_kernel(self):
        return self.application.kernel_manager

    def get_session(self, kernel_id):
        km = self.get_kernel()
        sm = km.get_session_manager(kernel_id)
        return sm


class KernelHandler(web.RequestHandler, BaseKernelHandler):

    def get(self):
        self.write(json.dumps(self.get_kernel().kernel_ids))

    def post(self, *args, **kwargs):
        kernel_id = kwargs['kernel_id']
        self.get_kernel().start_kernel(kernel_id)
        logging.info("Starting kernel: %s" % kernel_id)
        self.write(json.dumps(kernel_id))


class SessionHandler(web.RequestHandler, BaseKernelHandler):

    def get(self, *args, **kwargs):
        kernel_id = kwargs['kernel_id']
        self.write(json.dumps(self.get_session(kernel_id).session_ids))

    def post(self, *args, **kwargs):
        kernel_id = kwargs['kernel_id']
        sm = self.get_session(kernel_id)
        session_id = sm.start_session()
        logging.info("Starting session: %s, %s" % (kernel_id, session_id))
        self.write(json.dumps(session_id))


class ZMQStreamHandler(websocket.WebSocketHandler, BaseKernelHandler):

    stream_name = ''

    def open(self, *args, **kwargs):
        kernel_id = kwargs['kernel_id']
        session_id = kwargs['session_id']
        logging.info("Connection open: %s, %s" % (kernel_id,session_id))
        sm = self.get_session(kernel_id)
        method_name = "get_%s_stream" % self.stream_name
        method = getattr(sm, method_name)
        self.zmq_stream = method(session_id)
        self.zmq_stream.on_recv(self._on_zmq_reply)

    def on_message(self, msg):
        logging.info("Message received: %r" % msg)
        self.zmq_stream.send_unicode(msg)

    def on_close(self):
        self.zmq_stream.close()

    def _on_zmq_reply(self, msg):
        logging.info("Message reply: %r" % msg)
        self.write_message(msg)


class IOPubStreamHandler(ZMQStreamHandler):

    stream_name = 'iopub'


class ShellStreamHandler(ZMQStreamHandler):

    stream_name = 'shell'


class NotebookApplication(web.Application):

    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/kernels/%s" % (_kernel_id_regex,), KernelHandler),
            (r"/kernels/%s/sessions" % (_kernel_id_regex,), SessionHandler),
            (r"/kernels/%s/sessions/%s/iopub" % (_kernel_id_regex,_session_id_regex), IOPubStreamHandler),
            (r"/kernels/%s/sessions/%s/shell" % (_kernel_id_regex,_session_id_regex), ShellStreamHandler),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
        )
        web.Application.__init__(self, handlers, **settings)
        self.context = zmq.Context()
        self.kernel_manager = KernelManager(self.context)


def main():
    options.parse_command_line()
    application = NotebookApplication()
    http_server = httpserver.HTTPServer(application)
    http_server.listen(options.options.port)
    ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()

