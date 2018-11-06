from .mp_functions import print_exception, is_parent_process_alive, mark_task_done, LoopQueueSize, \
    stop_event_loop, run_loop, process_event, run_event_loop, run_consumer_loop, QUEUE_TIMEOUT
from .events import Event, CacheEvent, CacheObjectEvent, SaveVarEvent, VarEvent
from .mp_proxy import ProxyEvent, proxy_output_handler, Proxy
from .event_loop import EventLoop
try:
    from .async_event_loop import AsyncManager, AsyncEvent, AsyncEventLoop
except (ImportError, SyntaxError):
    pass
from .pool import Pool

from multiprocessing import freeze_support

import importlib


def use(lib):
    """Change the multiprocessing library that is being used.

    `multiprocess` and `multiprocessing_on_dill` are some alternatives, because normal pickling can be annoying.

    Note:
        This code does the same as

        ..code-block :: python

            >>> import mp_event_loop
            >>> # import multiprocess as mp
            >>> import multiprocessing as mp
            >>>
            >>> mp_event_loop.EventLoop.alive_event_class = mp.Event
            >>> mp_event_loop.EventLoop.queue_class = mp.JoinableQueue
            >>> mp_event_loop.EventLoop.event_loop_class = mp.Process
            >>>
            >>> loop = mp_event_loop.EventLoop()

    Args:
        lib (str/module): String module name to load or the module you want to use. The module should have an Event,
            JoinableQueue or Queue, and Process or Thread attributes to use.
    """
    if isinstance(lib, str):
        lib = importlib.import_module(lib)

    try:
        EventLoop.alive_event_class = lib.Event
    except AttributeError as err:
        print_exception(err, "Not able to change the alive_event_class (Event) using the library " + repr(lib))

    try:
        EventLoop.queue_class = lib.JoinableQueue
    except AttributeError:
        try:
            EventLoop.queue_class = lib.Queue
        except AttributeError as err:
            print_exception(err, "Not able to change the queue_class (Queue) using the library " + repr(lib))

    try:
        EventLoop.event_loop_class = lib.Process
    except AttributeError as err:
        try:
            EventLoop.event_loop_class = lib.Thread
        except AttributeError:
            print_exception(err, "Not able to change the event_loop_class (Process) using the library " + repr(lib))


# ========== Global Event Loop Functions ==========
DefaultEventLoop = EventLoop
GLOBAL_NAME = 'Global Event Loop'
__loop__ = None


def get_event_loop(output_handlers=None, event_queue=None, consumer_queue=None, initialize_process=None, name=None,
                   has_results=True):
    """Return the global event loop. If it does not exist create it. It will still need to be started or used as a
    context manager using the `with` statement.

    Args:
        output_handlers (list/tuple/callable)[None]: Function or list of funcs that process executed events with results.
        event_queue (Queue)[None]: Custom event queue for the event loop.
        consumer_queue (Queue)[None]: Custom consumer queue for the consumer process.
        initialize_process (function)[None]: Function to create and show widgets returning a dict of widgets and
            variable names to save for use.
        name (str)['main']: Event loop name. This name is passed to the event process and consumer process.
        has_results (bool)[True]: Should this event loop create a consumer process to run executed events
            through process_output.
    """
    if name is None:
        name = GLOBAL_NAME

    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(name=name, event_queue=event_queue, consumer_queue=consumer_queue,
                                    output_handlers=output_handlers, initialize_process=initialize_process,
                                    has_results=has_results)

    return __loop__


def add_output_handler(handler):
    """Add output handlers into the main global loop.

    The handler must be a callable that returns a boolean. If the handler returns True no other handlers after will
    be called.

    Args:
        handler (function/method): Returns True or False to stop propagating the event. Must take one event arg.
    """
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    return __loop__.add_output_handler(handler)


def insert_output_handler(index, handler):
    """Insert output handlers into the main global loop.

    The handler must be a callable that returns a boolean. If the handler returns True no other handlers after will
    be called.

    Args:
        index (int): Index position to insert the handler at.
        handler (function/method): Returns True or False to stop propagating the event. Must take one event arg.
    """
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    return __loop__.insert_output_handler(index, handler)


def add_event(target, *args, has_output=None, event_key=None, cache=False, re_register=False, start_loop=True,**kwargs):
    """Add an event to the main global loop to be run in a separate process.

    Args:
        target (function/method/callable/Event): Event or callable to run in a separate process.
        *args (tuple): Arguments to pass into the target function.
        has_output (bool) [False]: If True save the executed event and put it on the consumer/output queue.
        event_key (str)[None]: Key to identify the event or output result.
        cache (bool) [False]: If the target object should be cached.
        re_register (bool)[False]: Forcibly register this object in the other process.
        start_loop (bool)[True]: If True start running the event loop.
        **kwargs (dict): Keyword arguments to pass into the target function.
        args (tuple)[None]: Keyword args argument.
        kwargs (dict)[None]: Keyword kwargs argument.
    """
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    __loop__.add_event(target, *args, has_output=has_output, event_key=event_key, cache=cache,
                       re_register=re_register, **kwargs)

    if start_loop and not __loop__.is_running():
        __loop__.start()


def add_cache_event(target, *args, has_output=None, event_key=None, re_register=False, start_loop=True, **kwargs):
    """Add an event that uses cached objects to the main global loop.

    Args:
        target (function/method/callable/Event): Event or callable to run in a separate process.
        *args (tuple): Arguments to pass into the target function.
        has_output (bool) [False]: If True save the executed event and put it on the consumer/output queue.
        event_key (str)[None]: Key to identify the event or output result.
        re_register (bool)[False]: Forcibly register this object in the other process.
        start_loop (bool)[True]: If True start running the event loop.
        **kwargs (dict): Keyword arguments to pass into the target function.
        args (tuple)[None]: Keyword args argument.
        kwargs (dict)[None]: Keyword kwargs argument.
    """
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    __loop__.add_cache_event(target, *args, has_output=has_output, event_key=event_key,
                             re_register=re_register, **kwargs)

    if start_loop and not __loop__.is_running():
        __loop__.start()


def cache_object(*args, **kwargs):
    """Save an object in the separate processes, so the object can persist.

    Args:
        obj (object): Object to save in the separate process. This object will keep it's values between cache events
        has_output (bool)[False]: If True the cache object will be a result passed into the output_handlers.
        event_key (str)[None]: Key to identify the event or output result.
        re_register (bool)[False]: Forcibly register this object in the other process.
    """
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    __loop__.cache_object(*args, **kwargs)


def is_running():
    """Return if the main global loop is running."""
    global __loop__
    return __loop__ is not None and __loop__.is_running()


def start():
    """Start running the main global loop."""
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    if not __loop__.is_running():
        __loop__.start()


def run(events=None, output_handlers=None):
    """Run events on the global event loop and let the program continue.

    Args:
        events (list/tuple/Event): List of events to add to the event queue.
        output_handlers (list/tuple/callable): Function or list of functions to add as an output handler.
    """
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    return __loop__.run(events=events, output_handlers=output_handlers)


def run_until_complete(events=None, output_handlers=None):
    """Run the global event loop until all of the events are complete.

    Args:
        events (list/tuple/Event): List of events to add to the event queue.
        output_handlers (list/tuple/callable): Function or list of functions to add as an output handler.
    """
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    return __loop__.run_until_complete(events=events, output_handlers=output_handlers)


def wait():
    """Wait for the main global loop."""
    global __loop__
    if __loop__ is not None:
        __loop__.wait()


def stop():
    """Stop the main global loop from running."""
    global __loop__
    if __loop__ is not None:
        __loop__.stop()


def close():
    """Close the main global loop."""
    global __loop__
    if __loop__ is not None:
        __loop__.close()
