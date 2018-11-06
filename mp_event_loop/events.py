import types

__all__ = ['Event', 'CacheEvent', 'CacheObjectEvent', 'SaveVarEvent', 'VarEvent']


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
        self.results = None
        self.error = None
        if callable(self.target):
            # Run the command
            try:
                self.results = self.run()
            except Exception as err:
                self.error = err
        elif self.target is not None:
            self.error = ValueError("Invalid target (%s) given! Type %s" % (repr(self.target), str(type(self.target))))

    def __getstate__(self):
        """Return the state for pickling."""
        return {'target': self.target, 'args': self.args, 'kwargs': self.kwargs,
                'results': self.results, 'error': self.error,
                'has_output': self.has_output, 'event_key': self.event_key}

    def __setstate__(self, state):
        """Set the object's variables after pickling."""
        # Initialize variables
        self.target = state.get('target', None)
        self.args = state.get('args', tuple())
        self.kwargs = state.get('kwargs', {})

        self.results = state.get('results', None)
        self.error = state.get('error', None)
        self.has_output = state.get('has_output', False)
        self.event_key = state.get('event_key', None)


# ========== Cache Event ==========
class CacheEvent(Event):
    """Event that saves an object or command in the separate process to prevent passing the object back and forth
    between processes.
    """

    CACHE = {}
    DO_NOT_REGISTER_TYPE = (str, bytes, int, float, complex)

    @staticmethod
    def get_object_key(obj):
        """Return the object key used for accessing the object in the separate process."""
        if isinstance(obj, CacheEvent.DO_NOT_REGISTER_TYPE) or obj is None:
            return obj
        return str(id(obj))
        # return ":::".join((str(obj), str(id(obj))))

    @staticmethod
    def get_or_register_object(obj_id, obj):
        """Find and return the registered object or register the given object."""
        # Get the cache from the cache id
        if not isinstance(obj, CacheEvent.DO_NOT_REGISTER_TYPE) and obj is not None and obj_id not in CacheEvent.CACHE:
            CacheEvent.CACHE[obj_id] = obj
        return CacheEvent.CACHE.get(obj_id, obj)

    @classmethod
    def is_object_registered(cls, obj, name=None, cache=None):
        """Return if the object is registered."""
        if name is None:
            name = cls.get_object_key(obj)
        if cache is None:
            cache = CacheEvent.CACHE
        return obj is not None and cache.get(name, None) == obj

    @classmethod
    def register_object(cls, obj, name=None, cache=None):
        """Register the given object to the cache."""
        if name is None:
            name = cls.get_object_key(obj)
        if cache is None:
            cache = CacheEvent.CACHE
        cache[name] = obj
        return name

    def __init__(self, target, *args, has_output=True, event_key=None, cache=None, re_register=False, **kwargs):
        """Create the event.

        Args:
            target (function/method/callable): Object to run.
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            re_register (bool)[False]: Forcibly register this object in the other process.
            cache (dict)[None]: Custom cache dictionary.
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

        # Setup for multiple caches
        if cache is None:
            cache = CacheEvent.CACHE
        self.cache_id = CacheEvent.get_object_key(cache)
        self.cache = CacheEvent.get_or_register_object(self.cache_id, cache)

        # Set the Variables
        self.register = []
        self.object_id = self._cache_object_with_register(obj, re_register=re_register, cache=self.cache)
        self.method_name = cmd
        self.object = obj

        # Get the key for cached objects
        args = tuple(self._key_cached_object(arg, cache=self.cache) for arg in args)
        kwargs = {key: self._key_cached_object(val, cache=self.cache) for key, val in kwargs.items()}

        # Initialize
        super().__init__(target, *args, has_output=has_output, event_key=event_key, **kwargs)

    def _cache_object_with_register(self, obj, re_register=False, cache=None):
        """Check if the object is cached and register it to be cached.

        Args:
            obj (object): Object to be cached.
            re_register (bool)[False]: Forcibly register this object in the other process.
            cache (dict)[None]: Cache to check and register the object with.
        """
        if cache is None:
            cache = CacheEvent.CACHE

        # Check if the object needs to be created in the other process
        object_id = CacheEvent.get_object_key(obj)
        if not isinstance(obj, CacheEvent.DO_NOT_REGISTER_TYPE) and obj is not None and \
                (re_register or not CacheEvent.is_object_registered(obj, object_id, cache=cache)):
            CacheEvent.register_object(obj, object_id, cache=cache)
            self.register.append([object_id, obj])  # Name, object

        return object_id

    @staticmethod
    def _key_cached_object(obj, cache=None):
        """If the object is cached return the key for that object."""
        if cache is None:
            cache = CacheEvent.CACHE

        object_id = CacheEvent.get_object_key(obj)
        if not isinstance(obj, CacheEvent.DO_NOT_REGISTER_TYPE) and obj is not None and \
                CacheEvent.is_object_registered(obj, object_id, cache=cache):
            return object_id
        return obj

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
        # Normal Event variables
        state = super().__getstate__()
        state.pop('target', None)
        state.update({'cache_id': self.cache_id, 'register': self.register,
                      'object_id': self.object_id, 'method_name': self.method_name})
        return state

    def __setstate__(self, state):
        """Set the object variables after pickling.

        Register all of the cached items. Get the target from the target object_id and method_name.
        """
        super().__setstate__(state)

        # Initialize variables
        self.object = None
        self.object_id = None
        self.method_name = None

        # Get the cache from the cache id
        self.cache_id = state.get('cache_id', None)
        self.cache = CacheEvent.get_or_register_object(self.cache_id, CacheEvent.CACHE)

        # Register the items with the cache
        self.register = []
        register = state.get('register', [])
        if register:
            for name, obj in register:
                CacheEvent.register_object(obj, name=name, cache=self.cache)

        # Get the object_id and get the object from the object_id
        self.object_id = state.get('object_id', self.object_id)
        self.object = self.cache.get(self.object_id, self.object)

        # Get the target from the method name
        self.method_name = state.get('method_name', self.method_name)
        if self.method_name:
            self.target = getattr(self.object, self.method_name, None)
        else:
            self.target = self.object

        # Map cached args and kwargs
        self.args = tuple(self.cache.get(arg, arg) for arg in state.get('args', []))
        self.kwargs = {key: self.cache.get(val, val) for key, val in state.get('kwargs', {}).items()}


class CacheObjectEvent(CacheEvent):
    def __setstate__(self, state):
        super().__setstate__(state)
        # No not run a function. Only cache the object
        self.target = None


# ========== Variable Events ==========
class SaveVarEvent(CacheEvent):
    """Save the given object as the given variable name. You can then call methods on the object with the variable name
    using a VarEvent.
    """
    def __init__(self, create_func, *args, has_output=True, event_key=None, cache=None, re_register=False,
                 **kwargs):
        """Create the event.

        Args:
            create_func (callable): Function that will create variables and return a dictionary of
                variable name, object pairs.
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            re_register (bool)[False]: Forcibly register this object in the other process.
            cache (dict)[None]: Custom cache dictionary.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        super().__init__(create_func, *args, has_output=has_output, event_key=event_key,
                         cache=cache, re_register=re_register, **kwargs)

    def exec_(self):
        """Get the command and run it"""
        # Get the command to run
        self.results = None
        self.error = None
        if callable(self.target):
            # Run the command
            try:
                results = self.run()

                # Results should be a dictionary.
                for key, value in results.items():
                    CacheEvent.register_object(value, key, cache=self.cache)

                self.results = True

            except Exception as err:
                self.error = err
        elif self.target is None and self.object is not None:
            self.results = self.object
        else:
            self.error = ValueError("Invalid target (%s) given! Type %s" % (repr(self.target), str(type(self.target))))


class VarEvent(CacheEvent):
    """Run a method on a variable in a different process."""
    def __init__(self, var_name, method_name, *args, has_output=True, event_key=None, cache=None, re_register=False,
                 **kwargs):
        """Create the event.

        Args:
            var_name (str): Variable name or object id to access a cached object.
            method_name (str): Method name of the variable name to call with the given args and kwargs.
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            re_register (bool)[False]: Forcibly register this object in the other process.
            cache (dict)[None]: Custom cache dictionary.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        super().__init__(None, *args, has_output=has_output, event_key=event_key, cache=cache, re_register=re_register,
                         **kwargs)
        self.object_id = var_name
        self.method_name = method_name
