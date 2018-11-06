import atexit
import threading

import multiprocessing as mp

from .events import Event, CacheEvent, CacheObjectEvent, SaveVarEvent, VarEvent
from .mp_functions import print_exception, stop_event_loop, run_event_loop, run_consumer_loop


__all__ = ['EventLoop']


class EventLoop(object):
    """Event loop that runs in a separate process.

    This EventLoop has two main components a process and a thread. The process runs the events in a separate process.
    If the Event has results the event is put on the consumer_queue to be passed back into the main process. The thread
    runs a loop that waits for the event that were executed using the consumer_queue. The event is passed into
    EventLoop.process_output where multiple output_handlers can use the event and event.results/event.error.
    """

    alive_event_class = mp.Event
    queue_class = mp.JoinableQueue
    event_loop_class = mp.Process
    consumer_loop_class = threading.Thread

    run_event_loop = staticmethod(run_event_loop)
    run_consumer_loop = staticmethod(run_consumer_loop)

    def __init__(self, output_handlers=None, event_queue=None, consumer_queue=None, initialize_process=None,
                 name='main', has_results=True):
        """Create the event loop.

        Args:
            output_handlers (list/tuple/callable)[None]: Function or list of funcs that executed events with results.
            event_queue (Queue)[None]: Custom event queue for the event loop.
            consumer_queue (Queue)[None]: Custom consumer queue for the consumer process.
            initialize_process (function)[None]: Function to create and show widgets returning a dict of widgets and
                variable names to save for use.
            name (str)['main']: Event loop name. This name is passed to the event process and consumer process.
            has_results (bool)[True]: Should this event loop create a consumer process to run executed events
                through process_output.
        """
        if event_queue is None:
            event_queue = self.queue_class()
        if consumer_queue is None:
            consumer_queue = self.queue_class()

        if output_handlers is None:
            output_handlers = []
        elif not isinstance(output_handlers, (list, tuple)):
            output_handlers = [output_handlers]

        self.name = str(name)
        self.has_results = has_results
        self._needs_to_close = False

        self.alive_event = self.alive_event_class()
        self.event_queue = event_queue
        self.consumer_queue = consumer_queue
        self.event_process = None
        self.consumer_process = None  # Thread to handle results
        self.initialize_process = initialize_process

        self.cache = {}
        self.output_handlers = [hndlr for hndlr in output_handlers]

    # ========== Output Management ==========
    def add_output_handler(self, handler):
        """Add a function that handles the event output.

        The handler must be a callable that returns a boolean. If the handler returns True no other handlers after will
        be called.

        Args:
            handler (function/method): Returns True or False to stop propagating the event. Must take one event arg.
        """
        if handler not in self.output_handlers:
            self.output_handlers.append(handler)

    def insert_output_handler(self, index, handler):
        """Insert a function that handles the event output into a specific order.

        The handler must be a callable that returns a boolean. If the handler returns True no other handlers after will
        be called.

        Args:
            index (int): Index position to insert the handler at.
            handler (function/method): Returns True or False to stop propagating the event. Must take one event arg.
        """
        if handler in self.output_handlers:
            self.output_handlers.remove(handler)
        self.output_handlers.insert(index, handler)

    def process_output(self, event):
        """Override this function to handle executed events.

        Args:
            event (mp_event_loop.Event): Event that has results or error
        """
        if event.error:
            print_exception(event.error)
        else:
            for handler in self.output_handlers:
                if handler(event):
                    break

    # ========== Event Management ==========
    def add_event(self, target, *args, has_output=None, event_key=None, cache=False, re_register=False, **kwargs):
        """Add an event to be run in a separate process.

        Args:
            target (function/method/callable/Event): Event or callable to run in a separate process.
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the executed event and put it on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            cache (bool) [False]: If the target object should be cached.
            re_register (bool)[False]: Forcibly register this object in the other process.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        args = kwargs.pop('args', args)
        kwargs = kwargs.pop('kwargs', kwargs)

        if cache:
            return self.add_cache_event(target, *args, has_output=has_output, event_key=event_key,
                                        re_register=re_register, **kwargs)

        elif isinstance(target, Event):
            event = target

        else:
            if has_output is None:
                has_output = True
            event = Event(target, *args, has_output=has_output, event_key=event_key, **kwargs)

        self.event_queue.put(event)

    def add_cache_event(self, target, *args, has_output=None, event_key=None, re_register=False, **kwargs):
        """Add an event that uses cached objects.

        Args:
            target (function/method/callable/Event): Event or callable to run in a separate process.
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

        if isinstance(target, CacheEvent):
            event = target
        elif isinstance(target, Event):
            args = args or target.args
            kwargs = kwargs or target.kwargs
            has_output = has_output or target.has_output
            event_key = event_key or target.event_key
            target = target.target

            if has_output is None:
                has_output = True
            event = CacheEvent(target, *args, has_output=has_output, event_key=event_key, cache=self.cache,
                               re_register=re_register, **kwargs)
        else:
            if has_output is None:
                has_output = True
            event = CacheEvent(target, *args, has_output=has_output, event_key=event_key, cache=self.cache,
                               re_register=re_register, **kwargs)

        self.event_queue.put(event)

    def cache_object(self, obj, has_output=False, event_key=None, re_register=False):
        """Save an object in the separate processes, so the object can persist.

        Args:
            obj (object): Object to save in the separate process. This object will keep it's values between cache events
            has_output (bool)[False]: If True the cache object will be a result passed into the output_handlers.
            event_key (str)[None]: Key to identify the event or output result.
            re_register (bool)[False]: Forcibly register this object in the other process.
        """
        if isinstance(obj, CacheEvent):
            event = obj
        elif isinstance(obj, Event):
            old_event = obj
            obj = old_event.target
            event = CacheObjectEvent(obj, has_output=has_output, event_key=event_key,
                                     cache=self.cache, re_register=re_register)
            event.args = old_event.args
            event.kwargs = old_event.kwargs
            event.event_key = old_event.event_key
        else:
            event = CacheObjectEvent(obj, has_output=has_output, event_key=event_key,
                                     cache=self.cache, re_register=re_register)

        self.event_queue.put(event)

    def is_object_cached(self, obj):
        """Return if the object is in the cache."""
        return CacheEvent.is_object_registered(obj, cache=self.cache)

    def save_variables(self, create_func, *args, event_key=None, re_register=False, **kwargs):
        """

        Args:
            create_func (function/method/callable): Callable that creates variables and returns a dictionary of
                variable name, object paris.
            *args (tuple): Arguments to pass into the target function.
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

        if isinstance(create_func, CacheEvent):
            event = create_func
        elif isinstance(create_func, Event):
            old_event = create_func
            obj = old_event.target
            event = SaveVarEvent(obj, has_output=False, event_key=event_key,
                                 cache=self.cache, re_register=re_register)
            event.args = old_event.args
            event.kwargs = old_event.kwargs
            event.event_key = old_event.event_key
        else:
            event = SaveVarEvent(create_func, *args, has_output=False, event_key=event_key, cache=self.cache,
                                 re_register=re_register, **kwargs)

        return self.add_event(event)

    def add_var_event(self, var_name, target, *args, has_output=None, event_key=None, re_register=False, **kwargs):
        """Add an event to be run in a separate process.

        Args:
            var_name (str): Variable name.
            target (str/function/method/callable): Function or string object and function name.
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

        if isinstance(target, CacheEvent):
            event = target
        elif isinstance(target, Event):
            args = args or target.args
            kwargs = kwargs or target.kwargs
            has_output = has_output or target.has_output
            event_key = event_key or target.event_key
            target = target.target

            if has_output is None:
                has_output = True
            event = VarEvent(var_name, target, *args, has_output=has_output, event_key=event_key, cache=self.cache,
                             re_register=re_register, **kwargs)
        else:
            if has_output is None:
                has_output = True
            event = VarEvent(var_name, target, *args, has_output=has_output, event_key=event_key, cache=self.cache,
                             re_register=re_register, **kwargs)

        return self.add_event(event)

    # ========== Process Management ==========
    def is_running(self):
        """Return if the event loop is running."""
        return self.alive_event.is_set()

    def is_event_process_alive(self):
        """Return if the event process is alive."""
        try:
            return self.event_process.is_alive()
        except AttributeError:
            return False

    def is_consumer_process_alive(self):
        """Return if the consumer process is alive."""
        try:
            return self.consumer_process.is_alive()
        except AttributeError:
            return False

    def start(self):
        """Start running the separate process which runs an event loop."""
        self.close()

        # Create the separate Process
        self.start_event_loop()

        # Consumer Thread
        if self.has_results:
            self.start_consumer_loop()

        self._needs_to_close = True
        atexit.register(self.close)

    def start_event_loop(self):
        """Start running the event loop."""
        self.alive_event.set()
        self.event_process = self.event_loop_class(name="EventLoop-" + self.name, target=self.run_event_loop,
                                                   args=(self.alive_event, self.event_queue, self.consumer_queue),
                                                   kwargs={'initialize_process': self.initialize_process})
        self.event_process.daemon = True
        self.event_process.start()

    def start_consumer_loop(self):
        """Start running the consumer loop."""
        self.consumer_process = self.consumer_loop_class(name="ConsumerLoop-" + self.name,
                                                         target=self.run_consumer_loop,
                                                         args=(self.alive_event, self.consumer_queue,
                                                               self.process_output))
        self.consumer_process.daemon = True
        self.consumer_process.start()

    def run(self, events=None, output_handlers=None):
        """Run events on a separate process.

        Args:
            events (list/tuple/Event): List of events to add to the event queue.
            output_handlers (list/tuple/callable): Function or list of functions to add as an output handler.
        """
        # Add the output handlers
        if output_handlers:
            if not isinstance(output_handlers, (list, tuple)):
                self.add_output_handler(output_handlers)
            else:
                for hndlr in output_handlers:
                    self.add_output_handler(hndlr)

        # Add the events
        if events:
            if not isinstance(events, (list, tuple)):
                self.add_event(events)
            else:
                for event in events:
                    if isinstance(event, (list, tuple)):
                        self.add_event(*event)
                    elif isinstance(event, dict):
                        self.add_event(**event)
                    else:
                        self.add_event(event)

        # Start running
        if not self.is_running():
            self.start()

    def run_until_complete(self, events=None, output_handlers=None):
        """Run until all of the events are complete.

        Args:
            events (list/tuple/Event): List of events to add to the event queue.
            output_handlers (list/tuple/callable): Function or list of functions to add as an output handler.
        """
        self.run(events=events, output_handlers=output_handlers)
        self.close()

    def wait(self):
        """Wait for the event queue and consumer queue to finish processing."""
        try:
            if self.is_event_process_alive():
                self.event_queue.join()
        except AttributeError:
            pass

        try:
            if self.is_consumer_process_alive():
                self.consumer_queue.join()
        except AttributeError:
            pass

    def stop(self):
        """Stop running the process.

        Warning:
            This will also stop the logging
        """
        # If has_results clear and join the consumer queue and process
        kwargs = {}
        if self.has_results:
            kwargs['consumer_process'] = self.consumer_process
            self.consumer_process = None

        # Stop and clear the process and queue variables
        stop_event_loop(self.alive_event, self.event_process, **kwargs)
        self.event_process = None

    def close(self):
        """Close the event loop."""
        if not self._needs_to_close:
            return
        try:
            self._needs_to_close = False
            atexit.unregister(self.close)
        except:
            pass

        self.wait()
        self.stop()

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def __getstate__(self):
        return {'name': self.name, 'has_results': self.has_results,
                'output_handlers': self.output_handlers, 'process_output': self.process_output}

    def __setstate__(self, state):
        # Variables that are not saved
        self._needs_to_close = False
        self.event_process = None
        self.consumer_process = None
        self.event_queue = None
        self.consumer_queue = None
        self.cache = {}

        # Saved variables
        self.name = state.get('name', '')
        self.has_results = state.get('has_results', None)

    def __enter__(self):
        if not self.is_running():
            self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

        if exc_type is not None:
            return False
        return True
