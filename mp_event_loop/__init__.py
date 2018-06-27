from .mp_functions import print_exception, is_parent_process_alive, mark_task_done,\
    stop_event_loop, run_event_loop, run_consumer_loop
from .events import Event, CacheEvent
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
