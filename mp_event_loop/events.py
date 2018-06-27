

__all__ = ['EventResults', 'Event', 'CacheEvent']


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
    def __init__(self, target=None, args=None, kwargs=None, has_output=True, event_key=None):
        """Create the event.

        Args:
            target (function/method/callable): Object to run.
            args (tuple): Arguments to pass into the target function.
            kwargs (dict): Keyword arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
        """
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
        else:
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

    CLASS_CACHE = {}

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

    def get_process_object(self, name):
        """Find and return the global process object."""
        return self.cache.get(name, name)

    def __init__(self, target=None, args=None, kwargs=None, has_output=True, event_key=None, re_register=False,
                 cache=None):
        """Create the event.

        Args:
            target (function/method/callable): Object to run.
            args (tuple): Arguments to pass into the target function.
            kwargs (dict): Keyword arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            re_register (bool)[False]: Forcibly register this object in the other process.
            cache (dict)[None]: Specify a cache that you want to use.
        """
        if cache is None:
            cache = self.__class__.CLASS_CACHE
        self.cache = cache

        # Try to get the object from a method
        try:
            obj = target.__self__
            cmd = target.__name__
            if obj is None:
                obj = target
                cmd = None
        except AttributeError:
            obj = target
            cmd = None

        self.register = []
        self.method_name = cmd
        self.object_id = self.get_object_key(obj)

        # Check if the object needs to be created in the other process
        if re_register or not self.is_object_registered(obj, self.object_id):
            self.register_process_object(obj, self.object_id)
            self.register.append([self.object_id, obj])  # Name, object

        super().__init__(target=target, args=args, kwargs=kwargs, has_output=has_output, event_key=event_key)

    def __getstate__(self):
        """Return the state for pickling.

        Do not pass the target. Pass the items to be registered, the target object_id and method_name.
        """
        state = super().__getstate__()
        state.pop('target', None)
        state['object_id'] = self.object_id
        state['method_name'] = self.method_name
        state['register'] = self.register
        return state

    def __setstate__(self, state):
        """Set the object variables after pickling.

        Register all of the cached items. Get the target from the target object_id and method_name.
        """
        self.cache = self.__class__.CLASS_CACHE

        # Register the cached items
        self.register = []
        register = state.pop('register', None)
        if register:
            for name, obj in register:
                self.register_process_object(obj, name=name)

        # Get the target object_id and method_name
        self.object_id = state.pop('object_id', None)
        self.method_name = state.pop('method_name', None)

        # Find the target from the object_id and/or method_name
        target = self.get_process_object(self.object_id)
        if self.method_name is not None:
            target = getattr(target, self.method_name, None)
        state['target'] = target

        super().__setstate__(state)
