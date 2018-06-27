import os
import sys
import traceback

from .events import Event

try:
    import psutil
except ImportError as err:
    # _, _, exc_tb = sys.exc_info()
    # warning_msg = 'Please install psutil. The psutil library helps detect if the parent process has crashed.'
    # traceback.print_exception(ImportError, ImportError(warning_msg), exc_tb)
    psutil = None


__all__ = ['is_parent_process_alive', 'print_exception', 'stop_event_loop', 'run_event_loop', 'run_consumer_loop']


STOP_EXECUTION = "##=STOP EXECUTION===##"


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


def stop_event_loop(alive_event, event_queue=None, consumer_queue=None, event_process=None, consumer_process=None):
    """Stop the event loop and consumer loop.

    Args:
        alive_event (multiprocessing.Event): Event to signal that the process is closing and exit the loop.
        event_queue (multiprocessing.Queue/multiprocessing.JoinableQueue)[None]: Queue of events.
        consumer_queue (multiprocessing.Queue/multiprocessing.JoinableQueue)[None]: Queue of results to be processed.
        event_process (Process/Thread)[None]: Multiprocessing process to join and quit
        consumer_process (Thread/Process)[None]: Thread to join and quit. (Thread that consumes)
    """
    try:
        alive_event.clear()
    except AttributeError:
        pass

    # Stop the event loop
    try:
        event_queue.put(STOP_EXECUTION)
    except (AttributeError, Exception):
        pass
    try:
        event_process.join()
    except (AttributeError, Exception):
        pass

    # Stop the consumer loop
    try:
        consumer_queue.put(STOP_EXECUTION)
    except (AttributeError, Exception):
        pass
    try:
        consumer_process.join()
    except (AttributeError, Exception):
        pass


def run_event_loop(alive_event, event_queue, consumer_queue=None):
    """Run the event loop.

    Args:
        alive_event (multiprocessing.Event): Event to signal when to end the thread
        event_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to get and run events with
        consumer_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to pass results from the process
            to the thread.
    """
    # ===== Run the logging event loop =====
    while alive_event.is_set() and is_parent_process_alive():
        event = event_queue.get()
        if isinstance(event, Event):
            # Run the event
            event.exec_()
            if event.has_output:
                consumer_queue.put(event)

        mark_task_done(event_queue)

    # ===== Finish running the rest of the events before closing =====
    # Only handle the number of events at this point. Otherwise could run forever if queue.put is fast enough.
    for _ in range(event_queue.qsize()):
        event = event_queue.get()
        if isinstance(event, Event):
            # Run the command
            event.exec_()
            if event.has_output:
                consumer_queue.put(event)

        mark_task_done(event_queue)

    alive_event.clear()


def run_consumer_loop(alive_event, consumer_queue, process_output):
    """Run a loop to consume all of the output.

    Args:
        alive_event (multiprocessing.Event): Event to signal when to end the thread
        consumer_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to pass results from the process
            to the thread.
        process_output (callable): Function/method to consume the events.
    """
    while alive_event.is_set() and is_parent_process_alive():
        event = consumer_queue.get()
        if isinstance(event, Event):
            # Process the output
            process_output(event)

        mark_task_done(consumer_queue)

    # ===== Finish running the rest of the events before closing =====
    # Only handle the number of events at this point. Otherwise could run forever if queue.put is fast enough.
    for _ in range(consumer_queue.qsize()):
        event = consumer_queue.get()
        if isinstance(event, Event):
            # Process the output
            process_output(event)

        mark_task_done(consumer_queue)

    alive_event.clear()
