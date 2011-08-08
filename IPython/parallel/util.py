"""some generic utilities for dealing with classes, urls, and serialization

Authors:

* Min RK
"""
#-----------------------------------------------------------------------------
#  Copyright (C) 2010-2011  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

# Standard library imports.
import logging
import os
import re
import stat
import socket
import sys
from signal import signal, SIGINT, SIGABRT, SIGTERM
try:
    from signal import SIGKILL
except ImportError:
    SIGKILL=None

try:
    import cPickle
    pickle = cPickle
except:
    cPickle = None
    import pickle

# System library imports
import zmq
from zmq.log import handlers

# IPython imports
from IPython.config.application import Application
from IPython.utils.pickleutil import can, uncan, canSequence, uncanSequence
from IPython.utils.newserialized import serialize, unserialize
from IPython.zmq.log import EnginePUBHandler

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------

class Namespace(dict):
    """Subclass of dict for attribute access to keys."""
    
    def __getattr__(self, key):
        """getattr aliased to getitem"""
        if key in self.iterkeys():
            return self[key]
        else:
            raise NameError(key)

    def __setattr__(self, key, value):
        """setattr aliased to setitem, with strict"""
        if hasattr(dict, key):
            raise KeyError("Cannot override dict keys %r"%key)
        self[key] = value
    

class ReverseDict(dict):
    """simple double-keyed subset of dict methods."""
    
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self._reverse = dict()
        for key, value in self.iteritems():
            self._reverse[value] = key
    
    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self._reverse[key]
    
    def __setitem__(self, key, value):
        if key in self._reverse:
            raise KeyError("Can't have key %r on both sides!"%key)
        dict.__setitem__(self, key, value)
        self._reverse[value] = key
    
    def pop(self, key):
        value = dict.pop(self, key)
        self._reverse.pop(value)
        return value
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

#-----------------------------------------------------------------------------
# Functions
#-----------------------------------------------------------------------------

def asbytes(s):
    """ensure that an object is ascii bytes"""
    if isinstance(s, unicode):
        s = s.encode('ascii')
    return s

def validate_url(url):
    """validate a url for zeromq"""
    if not isinstance(url, basestring):
        raise TypeError("url must be a string, not %r"%type(url))
    url = url.lower()
    
    proto_addr = url.split('://')
    assert len(proto_addr) == 2, 'Invalid url: %r'%url
    proto, addr = proto_addr
    assert proto in ['tcp','pgm','epgm','ipc','inproc'], "Invalid protocol: %r"%proto
    
    # domain pattern adapted from http://www.regexlib.com/REDetails.aspx?regexp_id=391
    # author: Remi Sabourin
    pat = re.compile(r'^([\w\d]([\w\d\-]{0,61}[\w\d])?\.)*[\w\d]([\w\d\-]{0,61}[\w\d])?$')
    
    if proto == 'tcp':
        lis = addr.split(':')
        assert len(lis) == 2, 'Invalid url: %r'%url
        addr,s_port = lis
        try:
            port = int(s_port)
        except ValueError:
            raise AssertionError("Invalid port %r in url: %r"%(port, url))
        
        assert addr == '*' or pat.match(addr) is not None, 'Invalid url: %r'%url
        
    else:
        # only validate tcp urls currently
        pass
    
    return True


def validate_url_container(container):
    """validate a potentially nested collection of urls."""
    if isinstance(container, basestring):
        url = container
        return validate_url(url)
    elif isinstance(container, dict):
        container = container.itervalues()
    
    for element in container:
        validate_url_container(element)


def split_url(url):
    """split a zmq url (tcp://ip:port) into ('tcp','ip','port')."""
    proto_addr = url.split('://')
    assert len(proto_addr) == 2, 'Invalid url: %r'%url
    proto, addr = proto_addr
    lis = addr.split(':')
    assert len(lis) == 2, 'Invalid url: %r'%url
    addr,s_port = lis
    return proto,addr,s_port
    
def disambiguate_ip_address(ip, location=None):
    """turn multi-ip interfaces '0.0.0.0' and '*' into connectable
    ones, based on the location (default interpretation of location is localhost)."""
    if ip in ('0.0.0.0', '*'):
        try:
            external_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        except (socket.gaierror, IndexError):
            # couldn't identify this machine, assume localhost
            external_ips = []
        if location is None or location in external_ips or not external_ips:
            # If location is unspecified or cannot be determined, assume local
            ip='127.0.0.1'
        elif location:
            return location
    return ip

def disambiguate_url(url, location=None):
    """turn multi-ip interfaces '0.0.0.0' and '*' into connectable
    ones, based on the location (default interpretation is localhost).
    
    This is for zeromq urls, such as tcp://*:10101."""
    try:
        proto,ip,port = split_url(url)
    except AssertionError:
        # probably not tcp url; could be ipc, etc.
        return url
    
    ip = disambiguate_ip_address(ip,location)
    
    return "%s://%s:%s"%(proto,ip,port)

def serialize_object(obj, threshold=64e-6):
    """Serialize an object into a list of sendable buffers.
    
    Parameters
    ----------
    
    obj : object
        The object to be serialized
    threshold : float
        The threshold for not double-pickling the content.
        
    
    Returns
    -------
    ('pmd', [bufs]) :
        where pmd is the pickled metadata wrapper,
        bufs is a list of data buffers
    """
    databuffers = []
    if isinstance(obj, (list, tuple)):
        clist = canSequence(obj)
        slist = map(serialize, clist)
        for s in slist:
            if s.typeDescriptor in ('buffer', 'ndarray') or s.getDataSize() > threshold:
                databuffers.append(s.getData())
                s.data = None
        return pickle.dumps(slist,-1), databuffers
    elif isinstance(obj, dict):
        sobj = {}
        for k in sorted(obj.iterkeys()):
            s = serialize(can(obj[k]))
            if s.typeDescriptor in ('buffer', 'ndarray') or s.getDataSize() > threshold:
                databuffers.append(s.getData())
                s.data = None
            sobj[k] = s
        return pickle.dumps(sobj,-1),databuffers
    else:
        s = serialize(can(obj))
        if s.typeDescriptor in ('buffer', 'ndarray') or s.getDataSize() > threshold:
            databuffers.append(s.getData())
            s.data = None
        return pickle.dumps(s,-1),databuffers
            
        
def unserialize_object(bufs):
    """reconstruct an object serialized by serialize_object from data buffers."""
    bufs = list(bufs)
    sobj = pickle.loads(bufs.pop(0))
    if isinstance(sobj, (list, tuple)):
        for s in sobj:
            if s.data is None:
                s.data = bufs.pop(0)
        return uncanSequence(map(unserialize, sobj)), bufs
    elif isinstance(sobj, dict):
        newobj = {}
        for k in sorted(sobj.iterkeys()):
            s = sobj[k]
            if s.data is None:
                s.data = bufs.pop(0)
            newobj[k] = uncan(unserialize(s))
        return newobj, bufs
    else:
        if sobj.data is None:
            sobj.data = bufs.pop(0)
        return uncan(unserialize(sobj)), bufs

def pack_apply_message(f, args, kwargs, threshold=64e-6):
    """pack up a function, args, and kwargs to be sent over the wire
    as a series of buffers. Any object whose data is larger than `threshold`
    will not have their data copied (currently only numpy arrays support zero-copy)"""
    msg = [pickle.dumps(can(f),-1)]
    databuffers = [] # for large objects
    sargs, bufs = serialize_object(args,threshold)
    msg.append(sargs)
    databuffers.extend(bufs)
    skwargs, bufs = serialize_object(kwargs,threshold)
    msg.append(skwargs)
    databuffers.extend(bufs)
    msg.extend(databuffers)
    return msg

def unpack_apply_message(bufs, g=None, copy=True):
    """unpack f,args,kwargs from buffers packed by pack_apply_message()
    Returns: original f,args,kwargs"""
    bufs = list(bufs) # allow us to pop
    assert len(bufs) >= 3, "not enough buffers!"
    if not copy:
        for i in range(3):
            bufs[i] = bufs[i].bytes
    cf = pickle.loads(bufs.pop(0))
    sargs = list(pickle.loads(bufs.pop(0)))
    skwargs = dict(pickle.loads(bufs.pop(0)))
    # print sargs, skwargs
    f = uncan(cf, g)
    for sa in sargs:
        if sa.data is None:
            m = bufs.pop(0)
            if sa.getTypeDescriptor() in ('buffer', 'ndarray'):
                # always use a buffer, until memoryviews get sorted out
                sa.data = buffer(m)
                # disable memoryview support
                # if copy:
                #     sa.data = buffer(m)
                # else:
                #     sa.data = m.buffer
            else:
                if copy:
                    sa.data = m
                else:
                    sa.data = m.bytes
    
    args = uncanSequence(map(unserialize, sargs), g)
    kwargs = {}
    for k in sorted(skwargs.iterkeys()):
        sa = skwargs[k]
        if sa.data is None:
            m = bufs.pop(0)
            if sa.getTypeDescriptor() in ('buffer', 'ndarray'):
                # always use a buffer, until memoryviews get sorted out
                sa.data = buffer(m)
                # disable memoryview support
                # if copy:
                #     sa.data = buffer(m)
                # else:
                #     sa.data = m.buffer
            else:
                if copy:
                    sa.data = m
                else:
                    sa.data = m.bytes

        kwargs[k] = uncan(unserialize(sa), g)
    
    return f,args,kwargs

#--------------------------------------------------------------------------
# helpers for implementing old MEC API via view.apply
#--------------------------------------------------------------------------

def interactive(f):
    """decorator for making functions appear as interactively defined.
    This results in the function being linked to the user_ns as globals()
    instead of the module globals().
    """
    f.__module__ = '__main__'
    return f

@interactive
def _push(ns):
    """helper method for implementing `client.push` via `client.apply`"""
    globals().update(ns)

@interactive
def _pull(keys):
    """helper method for implementing `client.pull` via `client.apply`"""
    user_ns = globals()
    if isinstance(keys, (list,tuple, set)):
        for key in keys:
            if not user_ns.has_key(key):
                raise NameError("name '%s' is not defined"%key)
        return map(user_ns.get, keys)
    else:
        if not user_ns.has_key(keys):
            raise NameError("name '%s' is not defined"%keys)
        return user_ns.get(keys)

@interactive
def _execute(code):
    """helper method for implementing `client.execute` via `client.apply`"""
    exec code in globals()

#--------------------------------------------------------------------------
# extra process management utilities
#--------------------------------------------------------------------------

_random_ports = set()

def select_random_ports(n):
    """Selects and return n random ports that are available."""
    ports = []
    for i in xrange(n):
        sock = socket.socket()
        sock.bind(('', 0))
        while sock.getsockname()[1] in _random_ports:
            sock.close()
            sock = socket.socket()
            sock.bind(('', 0))
        ports.append(sock)
    for i, sock in enumerate(ports):
        port = sock.getsockname()[1]
        sock.close()
        ports[i] = port
        _random_ports.add(port)
    return ports

def signal_children(children):
    """Relay interupt/term signals to children, for more solid process cleanup."""
    def terminate_children(sig, frame):
        log = Application.instance().log
        log.critical("Got signal %i, terminating children..."%sig)
        for child in children:
            child.terminate()
        
        sys.exit(sig != SIGINT)
        # sys.exit(sig)
    for sig in (SIGINT, SIGABRT, SIGTERM):
        signal(sig, terminate_children)

def generate_exec_key(keyfile):
    import uuid
    newkey = str(uuid.uuid4())
    with open(keyfile, 'w') as f:
        # f.write('ipython-key ')
        f.write(newkey+'\n')
    # set user-only RW permissions (0600)
    # this will have no effect on Windows
    os.chmod(keyfile, stat.S_IRUSR|stat.S_IWUSR)


def integer_loglevel(loglevel):
    try:
        loglevel = int(loglevel)
    except ValueError:
        if isinstance(loglevel, str):
            loglevel = getattr(logging, loglevel)
    return loglevel

def connect_logger(logname, context, iface, root="ip", loglevel=logging.DEBUG):
    logger = logging.getLogger(logname)
    if any([isinstance(h, handlers.PUBHandler) for h in logger.handlers]):
        # don't add a second PUBHandler
        return
    loglevel = integer_loglevel(loglevel)
    lsock = context.socket(zmq.PUB)
    lsock.connect(iface)
    handler = handlers.PUBHandler(lsock)
    handler.setLevel(loglevel)
    handler.root_topic = root
    logger.addHandler(handler)
    logger.setLevel(loglevel)

def connect_engine_logger(context, iface, engine, loglevel=logging.DEBUG):
    logger = logging.getLogger()
    if any([isinstance(h, handlers.PUBHandler) for h in logger.handlers]):
        # don't add a second PUBHandler
        return
    loglevel = integer_loglevel(loglevel)
    lsock = context.socket(zmq.PUB)
    lsock.connect(iface)
    handler = EnginePUBHandler(engine, lsock)
    handler.setLevel(loglevel)
    logger.addHandler(handler)
    logger.setLevel(loglevel)
    return logger

def local_logger(logname, loglevel=logging.DEBUG):
    loglevel = integer_loglevel(loglevel)
    logger = logging.getLogger(logname)
    if any([isinstance(h, logging.StreamHandler) for h in logger.handlers]):
        # don't add a second StreamHandler
        return
    handler = logging.StreamHandler()
    handler.setLevel(loglevel)
    logger.addHandler(handler)
    logger.setLevel(loglevel)
    return logger

