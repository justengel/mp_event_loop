from .mp_functions import print_exception, is_parent_process_alive, mark_task_done,\
    stop_event_loop, run_event_loop, run_consumer_loop
from .events import EventResults, Event, CacheObjectEvent, CacheEvent
from .event_loop import EventLoop

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


def get_event_loop(name=None, event_queue=None, consumer_queue=None, output_handlers=None, has_results=True):
    """Return the global event loop. If it does not exist create it. It will still need to be started."""
    if name is None:
        name = GLOBAL_NAME

    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(name=name, event_queue=event_queue, consumer_queue=consumer_queue,
                                    output_handlers=output_handlers, has_results=has_results)

    return __loop__


def add_output_handler(handler):
    """Add output handlers into the main global loop."""
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    return __loop__.add_output_handler(handler)


def insert_output_handler(index, handler):
    """Insert output handlers into the main global loop."""
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    return __loop__.insert_output_handler(index, handler)


def add_event(*args, start_loop=True, **kwargs):
    """Add an event to the main global loop to be run in a separate process."""
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    return __loop__.add_event(*args, **kwargs)


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
    """Run events through the main global loop."""
    global __loop__
    if __loop__ is None:
        __loop__ = DefaultEventLoop(GLOBAL_NAME)

    return __loop__.run(events=events, output_handlers=output_handlers)


def run_until_complete(events=None, output_handlers=None):
    """Wait for the main global loop."""
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
