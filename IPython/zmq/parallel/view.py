"""Views of remote engines"""
#-----------------------------------------------------------------------------
#  Copyright (C) 2010  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

from IPython.utils.traitlets import HasTraits, Bool, List, Dict, Set, Int, Instance

from IPython.external.decorator import decorator
from IPython.zmq.parallel.asyncresult import AsyncResult
from IPython.zmq.parallel.dependency import Dependency
from IPython.zmq.parallel.remotefunction import ParallelFunction, parallel

#-----------------------------------------------------------------------------
# Decorators
#-----------------------------------------------------------------------------

@decorator
def myblock(f, self, *args, **kwargs):
    """override client.block with self.block during a call"""
    block = self.client.block
    self.client.block = self.block
    try:
        ret = f(self, *args, **kwargs)
    finally:
        self.client.block = block
    return ret

@decorator
def save_ids(f, self, *args, **kwargs):
    """Keep our history and outstanding attributes up to date after a method call."""
    n_previous = len(self.client.history)
    ret = f(self, *args, **kwargs)
    nmsgs = len(self.client.history) - n_previous
    msg_ids = self.client.history[-nmsgs:]
    self.history.extend(msg_ids)
    map(self.outstanding.add, msg_ids)
    return ret

@decorator
def sync_results(f, self, *args, **kwargs):
    """sync relevant results from self.client to our results attribute."""
    ret = f(self, *args, **kwargs)
    delta = self.outstanding.difference(self.client.outstanding)
    completed = self.outstanding.intersection(delta)
    self.outstanding = self.outstanding.difference(completed)
    for msg_id in completed:
        self.results[msg_id] = self.client.results[msg_id]
    return ret

@decorator
def spin_after(f, self, *args, **kwargs):
    """call spin after the method."""
    ret = f(self, *args, **kwargs)
    self.spin()
    return ret

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------

class View(HasTraits):
    """Base View class for more convenint apply(f,*args,**kwargs) syntax via attributes.
    
    Don't use this class, use subclasses.
    """
    block=Bool(False)
    bound=Bool(False)
    history=List()
    outstanding = Set()
    results = Dict()
    client = Instance('IPython.zmq.parallel.client.Client')
    
    _ntargets = Int(1)
    _balanced = Bool(False)
    _default_names = List(['block', 'bound'])
    _targets = None
    
    def __init__(self, client=None, targets=None):
        super(View, self).__init__(client=client)
        self._targets = targets
        self._ntargets = 1 if isinstance(targets, (int,type(None))) else len(targets)
        self.block = client.block
        
        for name in self._default_names:
            setattr(self, name, getattr(self, name, None))
        

    def __repr__(self):
        strtargets = str(self._targets)
        if len(strtargets) > 16:
            strtargets = strtargets[:12]+'...]'
        return "<%s %s>"%(self.__class__.__name__, strtargets)

    @property
    def targets(self):
        return self._targets

    @targets.setter
    def targets(self, value):
        raise AttributeError("Cannot set View `targets` after construction!")
    
    def _defaults(self, *excludes):
        """return dict of our default attributes, excluding names given."""
        d = dict(balanced=self._balanced, targets=self.targets)
        for name in self._default_names:
            if name not in excludes:
                d[name] = getattr(self, name)
        return d
    
    def set_flags(self, **kwargs):
        """set my attribute flags by keyword.
        
        A View is a wrapper for the Client's apply method, but
        with attributes that specify keyword arguments, those attributes
        can be set by keyword argument with this method.
        
        Parameters
        ----------
        
        block : bool
            whether to wait for results
        bound : bool
            whether to use the client's namespace
        """
        for key in kwargs:
            if key not in self._default_names:
                raise KeyError("Invalid name: %r"%key)
        for name in ('block', 'bound'):
            if name in kwargs:
                setattr(self, name, kwargs)
    
    #----------------------------------------------------------------
    # wrappers for client methods:
    #----------------------------------------------------------------
    @sync_results
    def spin(self):
        """spin the client, and sync"""
        self.client.spin()
    
    @sync_results
    @save_ids
    def apply(self, f, *args, **kwargs):
        """calls f(*args, **kwargs) on remote engines, returning the result.
        
        This method does not involve the engine's namespace.
        
        if self.block is False:
            returns msg_id
        else:
            returns actual result of f(*args, **kwargs)
        """
        return self.client.apply(f, args, kwargs, **self._defaults())

    @save_ids
    def apply_async(self, f, *args, **kwargs):
        """calls f(*args, **kwargs) on remote engines in a nonblocking manner.
        
        This method does not involve the engine's namespace.
        
        returns msg_id
        """
        d = self._defaults('block', 'bound')
        return self.client.apply(f,args,kwargs, block=False, bound=False, **d)

    @spin_after
    @save_ids
    def apply_sync(self, f, *args, **kwargs):
        """calls f(*args, **kwargs) on remote engines in a blocking manner,
         returning the result.
        
        This method does not involve the engine's namespace.
        
        returns: actual result of f(*args, **kwargs)
        """
        d = self._defaults('block', 'bound')
        return self.client.apply(f,args,kwargs, block=True, bound=False, **d)

    @sync_results
    @save_ids
    def apply_bound(self, f, *args, **kwargs):
        """calls f(*args, **kwargs) bound to engine namespace(s).
        
        if self.block is False:
            returns msg_id
        else:
            returns actual result of f(*args, **kwargs)
        
        This method has access to the targets' globals
        
        """
        d = self._defaults('bound')
        return self.client.apply(f, args, kwargs, bound=True, **d)

    @sync_results
    @save_ids
    def apply_async_bound(self, f, *args, **kwargs):
        """calls f(*args, **kwargs) bound to engine namespace(s) 
        in a nonblocking manner.
        
        returns: msg_id
        
        This method has access to the targets' globals
        
        """
        d = self._defaults('block', 'bound')
        return self.client.apply(f, args, kwargs, block=False, bound=True, **d)

    @spin_after
    @save_ids
    def apply_sync_bound(self, f, *args, **kwargs):
        """calls f(*args, **kwargs) bound to engine namespace(s), waiting for the result.
        
        returns: actual result of f(*args, **kwargs)
        
        This method has access to the targets' globals
        
        """
        d = self._defaults('block', 'bound')
        return self.client.apply(f, args, kwargs, block=True, bound=True, **d)
    
    def abort(self, msg_ids=None, block=None):
        """Abort jobs on my engines.
        
        Parameters
        ----------
        
        msg_ids : None, str, list of strs, optional
            if None: abort all jobs.
            else: abort specific msg_id(s).
        """
        block = block if block is not None else self.block
        return self.client.abort(msg_ids=msg_ids, targets=self.targets, block=block)

    def queue_status(self, verbose=False):
        """Fetch the Queue status of my engines"""
        return self.client.queue_status(targets=self.targets, verbose=verbose)
    
    def purge_results(self, msg_ids=[], targets=[]):
        """Instruct the controller to forget specific results."""
        if targets is None or targets == 'all':
            targets = self.targets
        return self.client.purge_results(msg_ids=msg_ids, targets=targets)
        
    #-------------------------------------------------------------------
    # Decorators
    #-------------------------------------------------------------------
    def parallel(self, bound=True, block=True):
        """Decorator for making a ParallelFunction"""
        return parallel(self.client, bound=bound, targets=self.targets, block=block, balanced=self._balanced)
    
    def remote(self, bound=True, block=True):
        """Decorator for making a RemoteFunction"""
        return parallel(self.client, bound=bound, targets=self.targets, block=block, balanced=self._balanced)
    


class DirectView(View):
    """Direct Multiplexer View of one or more engines.
    
    These are created via indexed access to a client:
    
    >>> dv_1 = client[1]
    >>> dv_all = client[:]
    >>> dv_even = client[::2]
    >>> dv_some = client[1:3]
    
    This object provides dictionary access to engine namespaces:
    
    # push a=5:
    >>> dv['a'] = 5 
    # pull 'foo':
    >>> db['foo']
    
    """
    
    def __init__(self, client=None, targets=None):
        super(DirectView, self).__init__(client=client, targets=targets)
        self._balanced = False
    
    @spin_after
    @save_ids
    def map(self, f, *sequences, **kwargs):
        """Parallel version of builtin `map`, using this View's `targets`.
        
        There will be one task per target, so work will be chunked
        if the sequences are longer than `targets`.  
        
        Results can be iterated as they are ready, but will become available in chunks.
        
        Parameters
        ----------
        
        f : callable
            function to be mapped
        *sequences: one or more sequences of matching length
            the sequences to be distributed and passed to `f`
        block : bool
            whether to wait for the result or not [default self.block]
        bound : bool
            whether to wait for the result or not [default self.bound]
        
        Returns
        -------
        
        if block=False:
            AsyncMapResult
                An object like AsyncResult, but which reassembles the sequence of results
                into a single list. AsyncMapResults can be iterated through before all
                results are complete.
            else:
                the result of map(f,*sequences)
        """
        
        block = kwargs.get('block', self.block)
        bound = kwargs.get('bound', self.bound)
        for k in kwargs.keys():
            if k not in ['block', 'bound']:
                raise TypeError("invalid keyword arg, %r"%k)
        
        assert len(sequences) > 0, "must have some sequences to map onto!"
        pf = ParallelFunction(self.client, f, block=block,
                        bound=bound, targets=self.targets, balanced=False)
        return pf.map(*sequences)
    
    def map_async(self, f, *sequences, **kwargs):
        """Parallel version of builtin `map`, using this view's engines."""
        if 'block' in kwargs:
            raise TypeError("map_async doesn't take a `block` keyword argument.")
        kwargs['block'] = True
        return self.map(f,*sequences,**kwargs)
    
    @sync_results
    @save_ids
    def execute(self, code, block=True):
        """execute some code on my targets."""
        return self.client.execute(code, block=block, targets=self.targets)
    
    def update(self, ns):
        """update remote namespace with dict `ns`"""
        return self.client.push(ns, targets=self.targets, block=self.block)
    
    push = update
    
    def get(self, key_s):
        """get object(s) by `key_s` from remote namespace
        will return one object if it is a key.
        It also takes a list of keys, and will return a list of objects."""
        # block = block if block is not None else self.block
        return self.client.pull(key_s, block=True, targets=self.targets)
    
    @sync_results
    @save_ids
    def pull(self, key_s, block=True):
        """get object(s) by `key_s` from remote namespace
        will return one object if it is a key.
        It also takes a list of keys, and will return a list of objects."""
        block = block if block is not None else self.block
        return self.client.pull(key_s, block=block, targets=self.targets)
    
    def scatter(self, key, seq, dist='b', flatten=False, targets=None, block=None):
        """
        Partition a Python sequence and send the partitions to a set of engines.
        """
        block = block if block is not None else self.block
        targets = targets if targets is not None else self.targets
        
        return self.client.scatter(key, seq, dist=dist, flatten=flatten,
                    targets=targets, block=block)
    
    @sync_results
    @save_ids
    def gather(self, key, dist='b', targets=None, block=None):
        """
        Gather a partitioned sequence on a set of engines as a single local seq.
        """
        block = block if block is not None else self.block
        targets = targets if targets is not None else self.targets
        
        return self.client.gather(key, dist=dist, targets=targets, block=block)
    
    def __getitem__(self, key):
        return self.get(key)
    
    def __setitem__(self,key, value):
        self.update({key:value})
    
    def clear(self, block=False):
        """Clear the remote namespaces on my engines."""
        block = block if block is not None else self.block
        return self.client.clear(targets=self.targets, block=block)
    
    def kill(self, block=True):
        """Kill my engines."""
        block = block if block is not None else self.block
        return self.client.kill(targets=self.targets, block=block)
    
    #----------------------------------------
    # activate for %px,%autopx magics
    #----------------------------------------
    def activate(self):
        """Make this `View` active for parallel magic commands.
        
        IPython has a magic command syntax to work with `MultiEngineClient` objects.
        In a given IPython session there is a single active one.  While
        there can be many `Views` created and used by the user, 
        there is only one active one.  The active `View` is used whenever 
        the magic commands %px and %autopx are used.
        
        The activate() method is called on a given `View` to make it 
        active.  Once this has been done, the magic commands can be used.
        """
        
        try:
            # This is injected into __builtins__.
            ip = get_ipython()
        except NameError:
            print "The IPython parallel magics (%result, %px, %autopx) only work within IPython."
        else:
            pmagic = ip.plugin_manager.get_plugin('parallelmagic')
            if pmagic is not None:
                pmagic.active_multiengine_client = self
            else:
                print "You must first load the parallelmagic extension " \
                      "by doing '%load_ext parallelmagic'"

    
class LoadBalancedView(View):
    """An load-balancing View that only executes via the Task scheduler.
    
    Load-balanced views can be created with the client's `view` method:
    
    >>> v = client.view(balanced=True)
    
    or targets can be specified, to restrict the potential destinations:
    
    >>> v = client.view([1,3],balanced=True)
    
    which would restrict loadbalancing to between engines 1 and 3.
    
    """
    
    _apply_name = 'apply_balanced'
    _default_names = ['block', 'bound', 'follow', 'after', 'timeout']
    
    def __init__(self, client=None, targets=None):
        super(LoadBalancedView, self).__init__(client=client, targets=targets)
        self._ntargets = 1
    
    def _validate_dependency(self, dep):
        """validate a dependency.
        
        For use in `set_flags`.
        """
        if dep is None or isinstance(dep, (str, AsyncResult, Dependency)):
            return True
        elif isinstance(dep, (list,set, tuple)):
            for d in dep:
                if not isinstance(d, str, AsyncResult):
                    return False
        elif isinstance(dep, dict):
            if set(dep.keys()) != set(Dependency().as_dict().keys()):
                return False
            if not isinstance(dep['msg_ids'], list):
                return False
            for d in dep['msg_ids']:
                if not isinstance(d, str):
                    return False
        else:
            return False
                
    def set_flags(self, **kwargs):
        """set my attribute flags by keyword.
        
        A View is a wrapper for the Client's apply method, but
        with attributes that specify keyword arguments, those attributes
        can be set by keyword argument with this method.
        
        Parameters
        ----------
        
        block : bool
            whether to wait for results
        bound : bool
            whether to use the engine's namespace
        follow : Dependency, list, msg_id, AsyncResult
            the location dependencies of tasks
        after : Dependency, list, msg_id, AsyncResult
            the time dependencies of tasks
        timeout : int,None
            the timeout to be used for tasks
        """
        
        super(LoadBalancedView, self).set_flags(**kwargs)
        for name in ('follow', 'after'):
            if name in kwargs:
                value = kwargs[name]
                if self._validate_dependency(value):
                    setattr(self, name, value)
                else:
                    raise ValueError("Invalid dependency: %r"%value)
        if 'timeout' in kwargs:
            t = kwargs['timeout']
            if not isinstance(t, (int, long, float, None)):
                raise TypeError("Invalid type for timeout: %r"%type(t))
            if t is not None:
                if t < 0:
                    raise ValueError("Invalid timeout: %s"%t)
            self.timeout = t
                
    @spin_after
    @save_ids
    def map(self, f, *sequences, **kwargs):
        """Parallel version of builtin `map`, load-balanced by this View.
        
        Each element will be a separate task, and will be load-balanced.  This
        lets individual elements be available for iteration as soon as they arrive.
        
        Parameters
        ----------
        
        f : callable
            function to be mapped
        *sequences: one or more sequences of matching length
            the sequences to be distributed and passed to `f`
        block : bool
            whether to wait for the result or not [default self.block]
        bound : bool
            whether to use the engine's namespace
        
        Returns
        -------
        
        if block=False:
            AsyncMapResult
                An object like AsyncResult, but which reassembles the sequence of results
                into a single list. AsyncMapResults can be iterated through before all
                results are complete.
            else:
                the result of map(f,*sequences)
        
        """
        
        block = kwargs.get('block', self.block)
        bound = kwargs.get('bound', self.bound)
        
        assert len(sequences) > 0, "must have some sequences to map onto!"
        
        pf = ParallelFunction(self.client, f, block=block, bound=bound, 
                                targets=self.targets, balanced=True)
        return pf.map(*sequences)
    
    def map_async(self, f, *sequences, **kwargs):
        """Parallel version of builtin `map`, using this view's engines.
        
        This is equivalent to map(...block=False)
        
        See `map` for details.
        """
        
        if 'block' in kwargs:
            raise TypeError("map_async doesn't take a `block` keyword argument.")
        kwargs['block'] = True
        return self.map(f,*sequences,**kwargs)
    
    
