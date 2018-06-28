import atexit
import threading

import multiprocessing as mp

from .events import Event, CacheEvent
from .mp_functions import print_exception, stop_event_loop, run_event_loop, run_consumer_loop


__all__ = ['EventLoop']


class EventLoop(object):
    """Event loop that runs in a separate process.

    This EventLoop has two main components a process and a thread. The process runs the events in a separate process.
    If the Event has results the event is put on the consumer_queue to be passed back into the main process. The thread
    runs a loop that waits for the event results using the consumer_queue. The event is passed into
    EventLoop.process_output where multiple output_handlers can use the results.
    10.162838401847281
    """

    alive_event_class = mp.Event
    queue_class = mp.JoinableQueue
    event_loop_class = mp.Process
    consumer_loop_class = threading.Thread

    run_event_loop = staticmethod(run_event_loop)
    run_consumer_loop = staticmethod(run_consumer_loop)

    def __init__(self, name='main', event_queue=None, consumer_queue=None, output_handlers=None, has_results=True):
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
        self.cache = {}

        self.alive_event = self.alive_event_class()
        self.event_queue = event_queue
        self.consumer_queue = consumer_queue
        self.event_process = None
        self.consumer_process = None  # Thread to handle results

        self.output_handlers = [hndlr for hndlr in output_handlers]

    # ========== Output Management ==========
    def add_output_handler(self, handler):
        """Add a function that handles the event output.

        The handler must be a callable that returns a boolean. If the handler returns True no other handlers after will
        be called.

        Args:
            handler (function/method): Returns True or False to stop propagating the event results. Must take one event
                argument.
        """
        self.output_handlers.append(handler)

    def insert_output_handler(self, index, handler):
        """Insert a function that handles the event output into a specific order.

        The handler must be a callable that returns a boolean. If the handler returns True no other handlers after will
        be called.

        Args:
            index (int): Index position to insert the handler at.
            handler (function/method): Returns True or False to stop propagating the event results. Must take one event
                argument.
        """
        self.output_handlers.insert(index, handler)

    def process_output(self, event_results):
        """Override this function to handle results.

        Args:
            event_results (mp_event_loop.EventResults): Event that has results or error
        """
        if event_results.error:
            print_exception(event_results.error)
        else:
            for handler in self.output_handlers:
                if handler(event_results):
                    break

    # ========== Event Management ==========
    def add_event(self, target, *args, has_output=None, event_key=None, cache=False, re_register=False, **kwargs):
        """Add an event to be run in a separate process.

        Args:
            target (function/method/callable/Event): Event or callable to run in a separate process.
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            cache (bool) [False]: If the target object should be cached.
            re_register (bool)[False]: Forcibly register this object in the other process.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        args = kwargs.pop('args', args)
        kwargs = kwargs.pop('kwargs', kwargs)

        if cache and isinstance(target, CacheEvent):
            event = target
        elif cache:
            if isinstance(target, Event):
                args = args or target.args
                kwargs = kwargs or target.kwargs
                has_output = has_output or target.has_output
                event_key = event_key or target.event_key
                target = target.target

            if has_output is None:
                has_output = True
            event = CacheEvent(target, *args, **kwargs, has_output=has_output, event_key=event_key,
                               re_register=re_register, cache=self.cache)

        elif isinstance(target, Event):
            event = target
        else:
            if has_output is None:
                has_output = True
            event = Event(target, *args, **kwargs, has_output=has_output, event_key=event_key)

        self.event_queue.put(event)

    # ========== Process Management ==========
    def is_running(self):
        """Return if the event loop is running."""
        return self.alive_event.is_set()

    def start(self):
        """Start running the separate process which runs an event loop."""
        self.stop()

        # Create the separate Process
        self.alive_event.set()
        self.event_process = self.event_loop_class(name="EventLoop-" + self.name, target=self.run_event_loop,
                                                   args=(self.alive_event, self.event_queue, self.consumer_queue))
        self.event_process.daemon = False
        self.event_process.start()

        # Consumer Thread
        if self.has_results:
            self.consumer_process = self.consumer_loop_class(name="ConsumerLoop-" + self.name,
                                                             target=self.run_consumer_loop,
                                                             args=(self.alive_event, self.consumer_queue,
                                                                   self.process_output))
            self.consumer_process.daemon = False
            self.consumer_process.start()

        self._needs_to_close = True
        atexit.register(self.stop)

    def run(self, events=None, output_handlers=None):
        """Run events through the main global loop."""
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
        """Run until all of the events are complete"""
        self.run(events=events, output_handlers=output_handlers)

        self.wait()
        self.stop()

    def wait(self):
        """Wait for the event queue and consumer queue to finish processing."""
        self.event_queue.join()
        self.consumer_queue.join()

    def stop(self):
        """Stop running the process.

        Warning:
            This will also stop the logging
        """
        try:
            self._needs_to_close = False
            atexit.unregister(self.stop)
        except:
            pass

        # If has_results clear and join the consumer queue and process
        kwargs = {}
        if self.has_results:
            kwargs['consumer_queue'] = self.consumer_queue
            kwargs['consumer_process'] = self.consumer_process
            self.consumer_process = None

        # Stop and clear the process and queue variables
        stop_event_loop(self.alive_event, self.event_queue, self.event_process, **kwargs)
        self.event_process = None

    def close(self):
        """Close the event loop."""
        self.stop()

    def __del__(self):
        try:
            if self._needs_to_close:
                self.close()
        except:
            pass

    def __getstate__(self):
        return {'output_handlers': self.output_handlers, 'process_output': self.process_output}

    def __setstate__(self, state):
        self.output_handlers = state.get('output_handlers', [])
        self.process_output = state.get('process_output', None)
        if self.process_output is None:
            self.process_output = self.__class__.process_output.__get__(self, self.__class__)

    def __enter__(self):
        if not self.is_running():
            self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.run_until_complete()

        if exc_type is not None:
            return False
        return True
