import collections
from functools import wraps
from .events import CacheEvent


__all__ = ['ProxyEvent', 'MpMethod', 'MpAttribute', 'proxy_func', 'proxy_output_handler', 'MpProxy']


class ProxyEvent(CacheEvent):
    """Cache event to help an object keep the same values as a cached object in a separate process."""

    def __init__(self, target, *args, properties=None, has_output=True, event_key=None, re_register=False, cache=None,
                 **kwargs):
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
        self.properties_values = {}
        self.properties = properties
        super().__init__(target, *args, has_output=has_output, event_key=event_key,
                         re_register=re_register, cache=cache, **kwargs)

    def exec_(self):
        """Get the command and run it"""
        # Get the command to run
        self.results = None
        self.error = None
        if callable(self.target):
            # Run the command
            try:
                self.results = self.run()
                if self.object and self.properties:
                    for prop in self.properties:
                        self.properties_values[prop] = getattr(self.object, prop)
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
        state['properties'] = self.properties
        state['properties_values'] = self.properties_values
        return state

    def __setstate__(self, state):
        """Set the object variables after pickling.

        Register all of the cached items. Get the target from the target object_id and method_name.
        """
        self.properties = state.pop('properties', None)
        self.properties_values = state.pop('properties_values', {})
        super().__setstate__(state)


class MpMethod(collections.namedtuple('MpAttribute', 'getter setter')):
    @staticmethod
    def get_obj_value(obj, getter):
        return getattr(obj, getter)()

    @staticmethod
    def set_obj_value(obj, setter, value):
        getattr(obj, setter)(value)

    def get_value(self, obj):
        return self.get_obj_value(obj, self.getter)

    def set_value(self, obj, value):
        self.set_obj_value(obj, self.setter, value)


class MpAttribute(collections.namedtuple('MpAttribute', 'name')):
    @staticmethod
    def get_obj_value(obj, getter):
        return getattr(obj, getter)

    @staticmethod
    def set_obj_value(obj, setter, value):
        setattr(obj, setter, value)

    def get_value(self, obj):
        return self.get_obj_value(obj, self.name)

    def set_value(self, obj, value):
        self.set_obj_value(obj, self.name, value)


def proxy_func(func=None, properties=None):
    """Decorator to make a function be called in a separate process."""
    if func is not None:
        name = func.__name__

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if hasattr(self, '__loop__') and self.__loop__:
                event = ProxyEvent(getattr(self, name), *args, **kwargs,
                                   properties=properties, cache=self.__loop__.cache)
                self.__loop__.add_cache_event(event)
            else:
                func(self, *args, **kwargs)

        return wrapper

    else:
        def new_decorator(func):
            name = func.__name__

            @wraps(func)
            def wrapper(self, *args, **kwargs):
                if hasattr(self, '__loop__') and self.__loop__:
                    event = ProxyEvent(getattr(self, name), *args, **kwargs,
                                       properties=properties, cache=self.__loop__.cache)
                    self.__loop__.add_cache_event(event)
                else:
                    func(self, *args, **kwargs)

            return wrapper

        return new_decorator


def proxy_output_handler(event):
    """Handle the proxy event"""
    if isinstance(event, ProxyEvent):
        for key, val in event.properties_values.items():
            setattr(event.object, key, val)
        return True


class MpProxy(object):
    """Multiprocessing proxy object.

    Set MP_METHOODS for getter and setter methods that should be transferred to the other process.
    Set MP_ATTRIBUTES for attributes/properties that should be transferred to the other process.

    Use the proxy_setter decorator to make that function be called in the other process.
    """

    MP_METHODS = []
    MP_ATTRIBUTES = []
    __loop__ = None

    def __init__(self, *args, loop=None, output_handler=proxy_output_handler, **kwargs):
        # Set the event loop
        if loop is None:
            loop = self.__class__.__loop__
        self.__loop__ = loop
        if self.__loop__ is not None:
            self.__loop__.add_output_handler(output_handler)

    def create_mp_objects(self):
        """Create objects and return a dictionary of variable name, object pairs."""
        return {}

    def set_mp_method(self, setter, value, properties=None):
        """Call a setter method in a separate process."""
        if hasattr(self, '__loop__') and self.__loop__:
            event = ProxyEvent(getattr(self, setter), value, properties=properties)
            self.__loop__.add_cache_event(event)
        else:
            getattr(self, setter)(value)

    def set_mp_attribute(self, attribute, value, properties=None):
        """Set the attribute in a a separate process."""
        if hasattr(self, '__loop__') and self.__loop__:
            event = ProxyEvent(self.__setattr__, attribute, value, properties=properties)
            self.__loop__.add_cache_event(event)
        else:
            setattr(self, attribute, value)

    def __getstate__(self):
        """Return the state for pickling to a separate process."""
        state = {
            'mp_attributes': {mp_item.name: mp_item.get_value(self) for mp_item in self.MP_ATTRIBUTES},
            'mp_methods': {mp_item.setter: mp_item.get_value(self) for mp_item in self.MP_METHODS},
            }
        return state

    def __setstate__(self, state):
        """Set the object variables after pickling in the separate process."""
        self.cache = CacheEvent.CACHE
        self.__loop__ = None

        # Create objects and save variables to the cache
        variables = self.create_mp_objects()
        if variables:
            for key, value in variables.items():
                self.cache[key] = value

        # Set the value for the attributes
        for key, val in state.pop('mp_attributes', {}).items():
            MpAttribute.set_obj_value(self, key, val)

        # set the value for the methods
        for key, val in state.pop('mp_methods', {}).items():
            MpMethod.set_obj_value(self, key, val)
