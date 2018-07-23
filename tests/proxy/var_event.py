from mp_event_loop import EventLoop, Event, CacheEvent, run_event_loop


__all__ = ['VarEvent', 'VarEventLoop']


class VarEvent(CacheEvent):
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


class VarEventLoop(EventLoop):
    def __init__(self, output_handlers=None, event_queue=None, consumer_queue=None, name='main',
                 initialize_process=None, has_results=True):
        """Create the event loop.

        Args:
            output_handlers (list/tuple/callable)[None]: Function or list of funcs that executed events with results.
            event_queue (Queue)[None]: Custom event queue for the event loop.
            consumer_queue (Queue)[None]: Custom consumer queue for the consumer process.
            name (str)['main']: Event loop name. This name is passed to the event process and consumer process.
            initialize_process (callable)[None]: Function to create objects and return a dictionary of
                variable name, object pairs.
            has_results (bool)[True]: Should this event loop create a consumer process to run executed events
                through process_output.
        """
        self.initialize_process = initialize_process
        super().__init__(output_handlers=output_handlers, event_queue=event_queue, consumer_queue=consumer_queue,
                         name=name, has_results=has_results)

    def add_var_event(self, var_name, method_name, *args, has_output=None, event_key=None, re_register=False, **kwargs):
        """Add an event to be run a method on an object that is cached with the given variable name.

        Args:
            var_name (str): Variable name or object id to access a cached object.
            method_name (str/function/method/callable): Function or string object and function name.
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the executed event and put it on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            re_register (bool)[False]: Forcibly register this object in the other process.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        args = kwargs.pop('args', args)
        kwargs = kwargs.pop('kwargs', kwargs)

        # Make sure cache is not a kwargs
        kwargs.pop('cache', None)

        if isinstance(var_name, Event):
            event = var_name

        else:
            if has_output is None:
                has_output = True
            event = VarEvent(var_name, method_name, *args, **kwargs, has_output=has_output, event_key=event_key,
                             cache=self.cache, re_register=re_register)

        return self.add_cache_event(event)

    def start_event_loop(self):
        """Start running the event loop."""
        self.alive_event.set()
        self.event_process = self.event_loop_class(name="EventLoop-" + self.name, target=self.run_event_loop,
                                                   args=(self.alive_event, self.event_queue, self.consumer_queue,
                                                         self.initialize_process))
        self.event_process.daemon = False
        self.event_process.start()

    @staticmethod
    def run_event_loop(alive_event, event_queue, consumer_queue=None, initialize_process=None):
        """Run the event loop.

        Args:
            alive_event (multiprocessing.Event): Event to signal when to end the thread
            event_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to get and run events with
            consumer_queue (multiprocessing.Queue/multiprocessing.JoinableQueue)[None]: Output queue of events.
            initialize_process (callable)[None]: Function to create objects and return a dictionary of
                variable name, object pairs.
        """
        # Initialize this process by creating cache variables that can be accessed with a VariableEvent
        if callable(initialize_process):
            variables = initialize_process()
            for key, val in variables.items():
                CacheEvent.register_object(val, key, cache=CacheEvent.CACHE)

        # ===== Run the logging event loop =====
        run_event_loop(alive_event, event_queue, consumer_queue)
