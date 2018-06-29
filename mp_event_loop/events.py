import types

__all__ = ['EventResults', 'Event', 'CacheObjectEvent', 'CacheEvent']


class EventResults(object):
    """Results object."""
    def __init__(self, results=None, error=None, event=None):
        self.results = results
        self.error = error
        self.event = event
        self.event_key = None

        if self.event is not None:
            self.event_key = self.event.event_key


class Event(object):
    """Basic event to run a function."""
    def __init__(self, target, *args, has_output=True, event_key=None, **kwargs):
        """Create the event.

        Args:
            target (function/method/callable): Object to run.
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        args = kwargs.pop('args', args)
        kwargs = kwargs.pop('kwargs', kwargs)

        self.target = target
        self.args = args or tuple()
        self.kwargs = kwargs or {}

        # Output variables
        self.results = None
        self.error = None
        self.has_output = has_output
        self.event_key = event_key

    def run(self):
        """Run the actual command that was given and return the results"""
        return self.target(*self.args, **self.kwargs)

    def exec_(self):
        """Get the command and run it"""
        # Get the command to run
        results = None
        error = None
        if callable(self.target):
            # Run the command
            try:
                results = self.run()
            except Exception as err:
                error = err
        elif self.target is not None:
            error = ValueError("Invalid target (%s) given! Type %s" % (repr(self.target), str(type(self.target))))

        return EventResults(results, error, self)

    def __getstate__(self):
        """Return the state for pickling."""
        return {'target': self.target, 'args': self.args, 'kwargs': self.kwargs,
                'results': self.results, 'error': self.error,
                'has_output': self.has_output, 'event_key': self.event_key}

    def __setstate__(self, state):
        """Set the object variables after pickling."""
        self.target = state.pop('target', None)
        self.args = state.pop('args', ())
        self.kwargs = state.pop('kwargs', {})

        self.results = state.pop('results', None)
        self.error = state.pop('error', None)

        self.has_output = state.pop('has_output', False)
        self.event_key = state.pop('event_key', None)


# ========== Cache Event ==========
class CacheEvent(Event):
    """Event that saves an object or command in the separate process to prevent passing the object back and forth
    between processes.
    """
    CACHE = {}

    @staticmethod
    def get_object_key(obj):
        """Return the object key used for accessing the object in the separate process."""
        if isinstance(obj, str) and ":::" in obj:
            return obj
        return ":::".join((str(obj), str(id(obj))))

    def is_object_registered(self, obj, name=None):
        """Return if the object is registered."""
        if name is None:
            name = self.get_object_key(obj)
        return obj is not None and self.cache.get(name, None) == obj

    def register_process_object(self, obj, name=None):
        """Register a global object which can be accessed.

        Warning:
            This should not be called manually! This is used by the CacheEvent. Manually calling this function may
            cause problems with registering objects in the separate process.
        """
        if name is None:
            name = self.get_object_key(obj)
        self.cache[name] = obj
        return name

    def _cache_object(self, obj, re_register=False):
        """Check if the object is cached and register it to be cached.

        Args:
            obj (object): Object to be cached.
            re_register (bool)[False]: Forcibly register this object in the other process.
        """
        # Check if the object needs to be created in the other process
        object_id = self.get_object_key(obj)
        if re_register or not self.is_object_registered(obj, object_id):
            self.register_process_object(obj, object_id)
            self.register.append([object_id, obj])  # Name, object

        return object_id

    def _key_cached_object(self, obj):
        """If the object is cached return the key for that object."""
        object_id = self.get_object_key(obj)
        if self.is_object_registered(obj, object_id):
            return object_id
        return obj

    def __init__(self, target, *args, has_output=True, event_key=None, re_register=False, cache=None, **kwargs):
        """Create the event.

        Args:
            target (function/method/callable): Object to run.
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            re_register (bool)[False]: Forcibly register this object in the other process.
            cache (dict)[None]: Specify a cache that you want to use.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        # Get proper args and kwargs
        args = kwargs.pop('args', args)
        kwargs = kwargs.pop('kwargs', kwargs)

        # Try to get the object from a method
        try:
            obj = target.__self__
            cmd = target.__name__
            if obj is None or isinstance(obj, types.ModuleType):
                obj = target
                cmd = None
        except AttributeError:
            obj = target
            cmd = None

        # Set the Variables
        self.cache = CacheEvent.CACHE
        if isinstance(cache, dict):
            self.cache = cache
        self.register = []
        self.object_id = self._cache_object(obj, re_register=re_register)
        self.method_name = cmd
        self.object = obj

        # Get the key for cached objects
        args = tuple(self._key_cached_object(arg) for arg in args)
        kwargs = {key: self._key_cached_object(val) for key, val in kwargs.items()}

        # Initialize
        super().__init__(target, *args, **kwargs, has_output=has_output, event_key=event_key)

    def __getstate__(self):
        """Return the state for pickling.

        Do not pass the target. Pass the items to be registered, the target object_id and method_name.
        """
        state = super().__getstate__()
        state['register'] = self.register
        state['object_id'] = self.object_id
        state['method_name'] = self.method_name
        state.pop('target', None)  # Do not pass the target anymore. Get the target from the object_id and method_name
        return state

    def __setstate__(self, state):
        """Set the object variables after pickling.

        Register all of the cached items. Get the target from the target object_id and method_name.
        """
        self.cache = CacheEvent.CACHE

        # Register the cached items
        self.register = []
        register = state.pop('register', None)
        if register:
            for name, obj in register:
                self.register_process_object(obj, name=name)

        # Get the target object_id and get the object from the object_id
        if not hasattr(self, 'object'):
            self.object = None
        if not hasattr(self, 'object_id'):
            self.object_id = None
        self.object_id = state.pop('object_id', self.object_id)
        self.object = self.cache.get(self.object_id, self.object)

        # Get the target from the method name
        if not hasattr(self, 'method_name'):
            self.method_name = None
        self.method_name = state.get('method_name', self.method_name)
        if self.method_name:
            state['target'] = getattr(self.object, self.method_name, None)
        else:
            state['target'] = self.object

        # Map cached args and kwargs
        try:
            state['args'] = tuple(self.cache.get(arg, arg) for arg in state['args'])
        except KeyError:
            pass
        try:
            state['kwargs'] = {key: self.cache.get(val, val) for key, val in state['kwargs'].items()}
        except KeyError:
            pass

        super().__setstate__(state)


class CacheObjectEvent(CacheEvent):
    """Event that registers and saves an object in the separate process. This event can also send the object back to
    the main process.
    """

    def __init__(self, obj, has_output=False, event_key=None, re_register=False, cache=None):
        """Create the event.

        Args:
            obj (object): Object to cache.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            re_register (bool)[False]: Forcibly register this object in the other process.
            cache (dict)[None]: Specify a cache that you want to use.
        """
        super().__init__(None, has_output=has_output, event_key=event_key, re_register=re_register, cache=cache)
        self.object_id = self._cache_object(obj, re_register=re_register)

    def exec_(self):
        """Get the command and run it"""
        # Get the command to run
        results = None
        error = None
        if callable(self.target):
            # Run the command
            try:
                results = self.run()
            except Exception as err:
                error = err
        elif self.target is None and self.object is not None:
            results = self.object
        else:
            error = ValueError("Invalid target (%s) given! Type %s" % (repr(self.target), str(type(self.target))))

        return EventResults(results, error, self)

    def __setstate__(self, state):
        """Set the object variables after pickling."""
        super().__setstate__(state)

        # This Event does not run a function, clear it if it was only caching an object
        if self.target == self.object:
            self.target = None
