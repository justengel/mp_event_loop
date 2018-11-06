import os
import sys
import traceback
from queue import Empty

from .events import Event, CacheEvent

try:
    import psutil
except ImportError as err:
    # _, _, exc_tb = sys.exc_info()
    # warning_msg = 'Please install psutil. The psutil library helps detect if the parent process has crashed.'
    # traceback.print_exception(ImportError, ImportError(warning_msg), exc_tb)
    psutil = None


__all__ = ['print_exception', 'is_parent_process_alive', 'mark_task_done', 'LoopQueueSize',
           'stop_event_loop', 'run_loop', 'process_event', 'run_event_loop', 'run_consumer_loop',
           'QUEUE_TIMEOUT']


QUEUE_TIMEOUT = 2


def print_exception(exc, msg=None):
    """Print the given exception. If a message is given it will be prepended to the exception message with a \n."""
    if msg:
        exc = "\n".join((msg, str(exc)))
    _, _, exc_tb = sys.exc_info()
    traceback.print_exception(exc.__class__, exc, exc_tb)


def is_parent_process_alive():
    """Return if the parent process is alive. This relies on psutil, but is optional."""
    if psutil is None:
        return True
    return psutil.pid_exists(os.getppid())


def mark_task_done(que):
    """Mark a JoinableQueue as done."""
    # Mark done
    try:
        que.task_done()
    except (AttributeError, ValueError):  # Value error if task_done called more times than put
        pass


class LoopQueueSize(object):
    """Iterator to iterate until the alive_event is cleared or the parent process dies then iterate the number of
    queue.qsize().
    """
    def __init__(self, alive_event, queue):
        self.queue = queue
        self.alive_event = alive_event
        self.countdown = -1

    def __iter__(self):
        self.countdown = -1
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        if self.countdown > 0:
            self.countdown -= 1
        elif self.countdown == 0:
            self.countdown = -1
            raise StopIteration
        else:
            should_iter = self.alive_event.is_set() and is_parent_process_alive()
            if not should_iter:
                self.countdown = self.queue.qsize()
                if self.countdown == 0:
                    self.countdown = -1
                    raise StopIteration
        return "Continue"


def stop_event_loop(alive_event, event_process=None, consumer_process=None):
    """Stop the event loop and consumer loop.

    Args:
        alive_event (multiprocessing.Event): Event to signal that the process is closing and exit the loop.
        event_process (Process/Thread)[None]: Multiprocessing process to join and quit
        consumer_process (Thread/Process)[None]: Thread to join and quit. (Thread that consumes)
    """
    try:
        alive_event.clear()
    except AttributeError:
        pass

    # Stop the event loop
    try:
        event_process.join()
    except (AttributeError, Exception):
        pass

    # Stop the consumer loop
    try:
        consumer_process.join()
    except (AttributeError, Exception):
        pass


def run_loop(process_queue_data, alive_event, event_queue, consumer_queue=None, initialize_process=None):
    """Run the event loop.

    Args:
        process_queue_data (function/callable): Function to process the data that comes off of the event queue.
            This function should take in 'consumer_queue' and 'variables' kwargs.
        alive_event (multiprocessing.Event): Event to signal when to end the thread
        event_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to get and run events with
        consumer_queue (multiprocessing.Queue/multiprocessing.JoinableQueue)[None]: Output queue of events.
        initialize_process (function)[None]: Function run at the start of the event loop. It should return a dictionary
            of variable name, object pairs.
    """
    # Create widgets and store the widgets
    variables = {}
    if callable(initialize_process):
        variables = initialize_process()

    # ===== Run the logging event loop =====
    for _ in LoopQueueSize(alive_event, event_queue):  # Iterate until a stop case then iterate the queue.qsize
        try:
            event = event_queue.get(timeout=QUEUE_TIMEOUT)
            try:
                process_queue_data(event, consumer_queue=consumer_queue, variables=variables)
            finally:  # Don't want the queue join to wait forever.
                mark_task_done(event_queue)
        except Empty:
            pass

    alive_event.clear()


def process_event(event, consumer_queue=None):
    """Process the given event.

    Args:
        event (Event): Event to execute
        even
        consumer_queue (Queue)[None]: Queue to put the results on.
    """
    if isinstance(event, Event):
        # Run the event
        event.exec_()
        if consumer_queue and event.has_output:
            consumer_queue.put(event)


def run_event_loop(alive_event, event_queue, consumer_queue=None, initialize_process=None):
    """Run the event loop.

    Args:
        alive_event (multiprocessing.Event): Event to signal when to end the thread
        event_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to get and run events with
        consumer_queue (multiprocessing.Queue/multiprocessing.JoinableQueue)[None]: Output queue of events.
        initialize_process (function)[None]: Function run at the start of the event loop. It should return a dictionary
            of variable name, object pairs.
    """
    # Create widgets and store the widgets
    cache = CacheEvent.CACHE  # This is the cache for this process
    if callable(initialize_process):
        variables = initialize_process()
        for key, val in variables.items():
            cache[key] = val

    # ===== Run the logging event loop =====
    for _ in LoopQueueSize(alive_event, event_queue):  # Iterate until a stop case then iterate the queue.qsize
        try:
            event = event_queue.get(timeout=QUEUE_TIMEOUT)
            try:
                process_event(event, consumer_queue=consumer_queue)
            finally:  # Don't want the queue join to wait forever.
                mark_task_done(event_queue)
        except Empty:
            pass

    alive_event.clear()


def run_consumer_loop(alive_event, consumer_queue, process_output):
    """Run a loop to consume all of the output.

    Args:
        alive_event (multiprocessing.Event): Event to signal when to end the thread
        consumer_queue (multiprocessing.Queue/multiprocessing.JoinableQueue)[None]: Output queue of events.
        process_output (callable): Function/method to consume the events.
    """
    for _ in LoopQueueSize(alive_event, consumer_queue):
        try:
            event = consumer_queue.get(timeout=QUEUE_TIMEOUT)
            try:
                if isinstance(event, Event):
                    # Process the output
                    process_output(event)
            finally:  # Don't want the queue join to wait forever.
                mark_task_done(consumer_queue)
        except Empty:
            pass

    alive_event.clear()
