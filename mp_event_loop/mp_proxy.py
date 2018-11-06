"""
Proxy an object by creating a new object in a separate process and accessing it's values in the main process.

This is a special fun challenge.

The main way this works is by keeping a cache (dictionary) which is a sort of global record of objects. You initially
create the proxy which stores a reference to the class of an object it is supposed to proxy. When the proxy is
initially created it sends an event to the event loop to cache the object. This sends an identifier for the cache,
loop, proxy, and sends an indicator letting the process know if the object needs to be the proxy or the real object.

The first time this is done the separate process will create the object (__setstate__). Once the object is created it
will register the object with the global cache. To sync values the other process needs to send the object back to the
main thread. This will send the state with identifiers for the cache, loop, and proxy as well a list of property
values and getter values. From the identifiers the object will find the correct cache and loop and will use the cache
to get the correct proxy object. The proxy object values will be set with the sent property and getter values.

Everything is handled with the passing back and forth of object to the other process and back to the main process.
This only works because of the sort of global caching system. I say sort of because each mp_event_loop.EventLoop has
it's own cache. In addition because there is a global cache at CacheEvent.CACHE each process uses this cache which is
separate from the main cache. We actually store each cache in the global CacheEvent.CACHE, so we can have separate
caches in the main process allowing multiple event loops with separate caches ... This systems basically saves
everything to cache and passes id's back and forth in order to keep track of objects.
"""
from .events import Event, CacheEvent


__all__ = ['ProxyEvent', 'proxy_output_handler', 'Proxy']


def _get_getter_value(func):
    """Return the getter function value or None."""
    try:
        return func()
    except:
        return None


class ProxyEvent(Event):
    """The ProxyEvent needs nothing done to it. All of the syncing and caching is done in the Proxy.__setstate__."""
    def __init__(self, obj, method_name=None, *args, has_output=True, event_key=None, **kwargs):
        """Create the event.

        Args:
            obj (Proxy): Object representing an id to run a method with.
            method_name (str): Method name for the object.
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        # Get proper args and kwargs
        args = kwargs.pop('args', args)
        kwargs = kwargs.pop('kwargs', kwargs)

        # Set the Variables
        self.object = obj  # This should be a Proxy object
        self.method_name = method_name

        # Initialize
        super().__init__(obj, *args, has_output=has_output, event_key=event_key, **kwargs)

    def exec_(self):
        """Get the command and run it"""
        # Get the command to run
        self.results = None
        self.error = None
        if callable(self.target):
            # Run the command
            try:
                self.results = self.run()
            except Exception as err:
                self.error = err
        elif self.target is None and self.object is not None:
            self.results = self.object
        else:
            self.error = ValueError("Invalid target (%s) given! Type %s" % (repr(self.target), str(type(self.target))))

    def __getstate__(self):
        """Return the state for pickling.

        Do not pass the target. Pass the items to be registered, the target object_id and method_name.
        """
        state = super().__getstate__()
        state['object'] = self.object
        state['method_name'] = self.method_name
        state.pop('target', None)  # Do not pass the target anymore. Get the target from the object_id and method_name
        return state

    def __setstate__(self, state):
        """Set the object variables after pickling.

        Register all of the cached items. Get the target from the target object_id and method_name.
        """
        super().__setstate__(state)

        self.object = state.pop('object', None)
        self.method_name = state.pop('method_name', None)
        if self.method_name:
            state['target'] = getattr(self.object, self.method_name, None)
        else:
            state['target'] = self.object

        super().__setstate__(state)


def proxy_output_handler(event):
    """Handle the proxy event output. Nothing needs to happen here. All of the syncing is done in Proxy.__setstate__."""
    if isinstance(event, ProxyEvent):
        return True


class Proxy(object):
    """This proxy works by defining the properties and getter methods that you want to me accessible in the main
    process while a different process holds the real object.

    Note:
        Proxy values take a long time to sync. This object is more for controlling and calling methods for an object
        that lives in a different process.
    """
    SLOTS = ['__cache_id__', '__loop_id__', '__proxy_id__', '__loop__',  '__cache__', '__proxy__', '__object__',
             '__args__', '__kwargs__',
             'PROXY_CLASS', 'PROPERTIES', 'GETTERS', 'SLOTS', 'create_mp_object']

    __loop__ = None

    # Required properties
    PROXY_CLASS = dict
    PROPERTIES = []
    GETTERS = []

    def create_mp_object(self, *args, **kwargs):
        """Take in known properties and getters and return a single object to exist in the separate process and be
        referenced by the proxy.

        Args:
            args (tuple): Tuple of proxy given arguments
            kwargs (dict): Dictionary of proxy given keyword arguments
        """
        return self.PROXY_CLASS(*args, **kwargs)

    def sync_mp_object(self):
        """Synchronize the multiprocessing object with the proxy. This should not need to be called."""
        if self.__loop__:
            # Try to make the proxy_output_handler run first
            if proxy_output_handler not in self.__loop__.output_handlers:
                self.__loop__.insert_output_handler(0, proxy_output_handler)

            # Automate starting the loop
            if not self.__loop__.is_running():
                self.__loop__.start()

            # Cache the object which should create the mp object if not created yet.
            self.__loop__.cache_object(self, has_output=True, event_key=self.__proxy_id__)

    @staticmethod
    def _call_in_process(loop, obj, method_name=None, *args, **kwargs):
        """Call the target function in a separate process."""
        if loop is not None:
            pe = ProxyEvent(obj, method_name, *args, **kwargs)
            loop.add_event(pe)
            return True
        return False

    def mp_wait(self):
        """Wait for all multiprocessing events. This makes this objects value sync."""
        self.__loop__.wait()

    def is_mp_proxy(self):
        """Return if this object is the proxy object that lives in the main process."""
        return bool(self.__proxy__)

    def __init__(self, *args, loop=None, **kwargs):
        # Check and set the event loop
        if loop is None:
            loop = self.__loop__
        if loop is None:
            raise ValueError("Invalid multiprocessing event loop for the proxy!")
        self.__loop_id__ = CacheEvent.get_object_key(loop)
        self.__loop__ = CacheEvent.get_or_register_object(self.__loop_id__, loop)

        # Check and set the cache
        try:
            cache = self.__loop__.cache
        except AttributeError:
            cache = CacheEvent.CACHE
        self.__cache_id__ = CacheEvent.get_object_key(cache)
        self.__cache__ = CacheEvent.get_or_register_object(self.__cache_id__, cache)

        # Set the main variables
        self.__args__ = tuple()
        self.__kwargs__ = {}
        self.__proxy__ = {None: None}
        self.__proxy_id__ = CacheEvent.register_object(self.__proxy__, cache=self.__cache__)
        self.__object__ = None

        # Initialize and create the object in a separate process
        self.initialize(*args, **kwargs)
        self.sync_mp_object()

    def initialize(self, *args, **kwargs):
        self.__args__ = args
        self.__kwargs__ = kwargs

    def __getattr__(self, item):
        try:
            proxy = self.__proxy__
            if proxy:
                if item in self.GETTERS:
                    def getter_func(*args, **kwargs):
                        return proxy.get(item, None)
                    return getter_func
                elif item in self.PROPERTIES or item in proxy:
                    return proxy.get(item, None)

                # Check if function should be called in a different process
                elif not item.startswith('__') and not item.endswith('__'):
                    def getter_call_in_process(*args, **kwargs):
                        self._call_in_process(self.__loop__, self, item, *args, **kwargs)
                    getter_call_in_process.__name__ = item
                    return getter_call_in_process
            else:
                # Object exists in a different process
                return getattr(self.__object__, item)
        except:
            pass
        raise AttributeError("'object' has no attribute " + repr(item))

    def __setattr__(self, key, value):
        try:
            if key in self.SLOTS:
                # Value belongs to this class
                return super().__setattr__(key, value)

            elif self.__proxy__:
                # Value belongs int the proxy
                self.__proxy__[key] = value

                # If setting a property set the property value in the separate process
                self._call_in_process(self.__loop__, self, '__setattr__', key, value)
                return
            else:
                # Object exists in a different process
                setattr(self.__object__, key, value)
                return
        except:
            pass

        return super().__setattr__(key, value)

    def __getstate__(self):
        # Is going to the separate process. If False is going to the main process which is the proxy
        is_target_other_process = self.is_mp_proxy()

        # State values to return
        state = {'__cache_id__': self.__cache_id__,
                 '__loop_id__': self.__loop_id__,
                 '__proxy_id__': self.__proxy_id__,
                 '__args__': self.__args__,
                 '__kwargs__': self.__kwargs__,
                 'is_other_process': is_target_other_process,
                 'SLOTS': self.SLOTS,
                 }

        if is_target_other_process:
            # May need to set the initial PROPERTIES and GETTERS value
            state['PROPERTIES'] = {name: None for name in self.PROPERTIES}
            state['GETTERS'] = {name: None for name in self.GETTERS}
        else:
            # May be the best way to sync values? or use event?
            state['PROPERTIES'] = {name: getattr(self.__object__, name, None) for name in self.PROPERTIES}
            state['GETTERS'] = {name: _get_getter_value(getattr(self.__object__, name, None)) for name in self.GETTERS}

        return state

    def __setstate__(self, state):
        # Get the loop and cache
        self.SLOTS = state['SLOTS']
        self.__cache_id__ = state['__cache_id__']
        self.__loop_id__ = state['__loop_id__']
        self.__proxy_id__ = state['__proxy_id__']
        self.__args__ = tuple()
        self.__kwargs__ = {}
        self.__proxy__ = None
        self.__object__ = None

        # Get the cache and loop
        self.__cache__ = CacheEvent.get_or_register_object(self.__cache_id__, CacheEvent.CACHE)
        self.__loop__ = CacheEvent.get_or_register_object(self.__loop_id__, None)

        # Get if this item is a proxy or real object in a different process
        proxy = self.__cache__.get(self.__proxy_id__, None)
        if state.get('is_other_process', False):
            if not proxy:
                # ===== Create the new object (One Time!) =====
                # Set the properties and getters once
                self.PROPERTIES = list(state.get('PROPERTIES', {}))
                self.GETTERS = list(state.get("GETTERS", {}))

                # Create the new object in this different process
                proxy = self.create_mp_object(*state['__args__'], **state['__kwargs__'])
                CacheEvent.register_object(proxy, cache=self.__cache__)
                self.__cache__[self.__proxy_id__] = proxy

            self.__object__ = proxy
        else:
            # Re-sync proxy attributes when this object is return to the main process
            for key, val in state.get('PROPERTIES', {}).items():
                proxy[key] = val

            for key, val in state.get('GETTERS', {}).items():
                proxy[key] = val

            self.__proxy__ = proxy
