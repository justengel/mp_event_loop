import sys
import copy
import inspect
import types

from queue import Empty

from .events import Event, CacheEvent
from .event_loop import EventLoop
from .mp_functions import mark_task_done, LoopQueueSize, QUEUE_TIMEOUT, is_parent_process_alive

__all__ = ['run_async_event_loop', 'AsyncEventLoop']


class AsyncManager(object):
    COROUTINES = {}

    @staticmethod
    def register(name, obj=None):
        """Register the object"""
        if obj is None:
            obj = name
            name = '.'.join((obj.__module__, obj.__name__))
        AsyncManager.COROUTINES[name] = obj

    @staticmethod
    def get(name):
        """Get the object from the given name."""
        if name not in AsyncManager.COROUTINES:
            try:
                module, name = name.split('.', 1)
                return getattr(sys.modules[module], name)
            except AttributeError:
                pass
        return AsyncManager.COROUTINES[name]


    @staticmethod
    def get_name(obj):
        """Get the registered name or sys.modules name."""
        if isinstance(obj, str):
            return obj

        try:
            idx = tuple(AsyncManager.COROUTINES.values()).index(obj)
            return tuple(AsyncManager.COROUTINES.keys())[idx]
        except ValueError:
            pass

        if obj.__module__ not in sys.modules:
            raise ValueError('Coroutine not registered! A Coroutine must be registered in the module level scope! '
                             'Coroutines are not picklable and cannot be sent to another process.')
        return '.'.join((obj.__module__, obj.__name__))


async def get_value_from_async(store, coro):
    """Wait for a result from the coroutine and store it in the given results list.

    Args:
        store (list): Object to store the results in
        coro (coroutine): Coroutine to wait on.
    """
    res = await coro
    store.append(res)


def get_async_results(coro):
    if inspect.isawaitable(coro):
        store = []
        try:
            get_value_from_async(store, coro).send(None)
        except StopIteration:
            pass
        if len(store):
            return store[0]
        return None
    return coro


class AsyncEvent(Event):
    def __init__(self, coroutine_name, *args, has_output=True, event_key=None, **kwargs):
        """Create the event.

        Args:
            coroutine_name (str/coroutine): Coroutine name or registered coroutine to lookup the name for
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [False]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        self.coroutine_name = AsyncManager.get_name(coroutine_name)
        target = AsyncManager.get(self.coroutine_name)
        super().__init__(target, *args, has_output=has_output, event_key=event_key, **kwargs)

    def run(self):
        results = self.target(*self.args, **self.kwargs)
        return get_async_results(results)

    def __getstate__(self):
        state = super().__getstate__()
        state['coroutine_name'] = self.coroutine_name
        state.pop('target', None)
        return state

    def __setstate__(self, state):
        super().__setstate__(state)

        self.coroutine_name = state.get('coroutine_name', '')
        self.target = AsyncManager.get(self.coroutine_name)


class LoopAsyncQueueSize(LoopQueueSize):
    """Iterator to iterate until the alive_event is cleared or the parent process dies then iterate the number of
    queue.qsize().
    """
    def __init__(self, alive_event, queue, async_generator_events):
        self.async_generator_events = async_generator_events
        super().__init__(alive_event, queue)

    def __next__(self):
        if self.countdown > 0:
            self.countdown -= 1
        elif len(self.async_generator_events):
            return "Continue Async"
        else:
            should_iter = self.alive_event.is_set() and is_parent_process_alive()
            if not should_iter:
                self.countdown = self.queue.qsize()
        if self.countdown == 0:
            raise StopIteration
        return "Continue"


def run_async_event_loop(alive_event, event_queue, consumer_queue=None, initialize_process=None):
    """Run the event loop.

    Args:
        alive_event (multiprocessing.Event): Event to signal when to end the thread
        event_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to get and run events with
        consumer_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to pass results from the process
            to the thread.
        initialize_process (function)[None]: Function run at the start of the event loop. It should return a dictionary
            of variable name, object pairs.
    """
    # Create widgets and store the widgets
    cache = CacheEvent.CACHE  # This is the cache for this process
    if callable(initialize_process):
        variables = initialize_process()
        for key, val in variables.items():
            cache[key] = val

    async_generator_events = []
    # ===== Run the logging event loop =====
    for _ in LoopAsyncQueueSize(alive_event, event_queue, async_generator_events):
        event = None
        if not event_queue.empty():
            event = event_queue.get_nowait()

        elif len(async_generator_events) == 0:
            # Get an event an run it
            try:
                event = event_queue.get(timeout=QUEUE_TIMEOUT)
            except Empty:
                pass

        if isinstance(event, Event):
            # Run the event
            event.exec_()
            if event.results and isinstance(event.results, types.CoroutineType):
                try:
                    event.results = event.results.send(None)  # The coroutine is finally called
                except StopIteration:
                    event.results = None

            if consumer_queue:
                if event.results and isinstance(event.results, types.AsyncGeneratorType):
                    event.async_generator = event.results
                    async_generator_events.append(event)

                elif event.has_output:
                    consumer_queue.put(event)
                    mark_task_done(event_queue)

        # Loop through the existing async_generators
        offset = 0
        for i in range(len(async_generator_events)):
            event = async_generator_events[i + offset]
            new_event = copy.copy(event)
            try:
                coro = event.async_generator.asend(None)
                new_event.results = get_async_results(coro)  # .send(None)
            except StopIteration:
                # Every coro.send call will cause a StopIteration
                continue
            except (StopAsyncIteration, AttributeError):
                # The async generator is complete
                async_generator_events.pop(i)
                offset -= 1
                mark_task_done(event_queue)
                continue
            except Exception as err:
                new_event.error = err

            # Put the results on the queue
            if consumer_queue and new_event.has_output:
                consumer_queue.put(new_event)

    alive_event.clear()


class AsyncEventLoop(EventLoop):
    """EventLoop to work with async/await coroutines."""
    run_event_loop = staticmethod(run_async_event_loop)

    def async_event(self, coroutine_name, *args, has_output=None, event_key=None, **kwargs):
        """Add an event to be run in a separate process.

        Args:
            coroutine_name (str/coroutine): Coroutine name or registered coroutine to lookup the name for
            *args (tuple): Arguments to pass into the target function.
            has_output (bool) [None]: If True save the results and put this event on the consumer/output queue.
            event_key (str)[None]: Key to identify the event or output result.
            **kwargs (dict): Keyword arguments to pass into the target function.
            args (tuple)[None]: Keyword args argument.
            kwargs (dict)[None]: Keyword kwargs argument.
        """
        args = kwargs.pop('args', args)
        kwargs = kwargs.pop('kwargs', kwargs)

        if isinstance(coroutine_name, Event):
            event = coroutine_name
        else:
            if has_output is None:
                has_output = True
            event = AsyncEvent(coroutine_name, *args, has_output=has_output, event_key=event_key, **kwargs)

        self.event_queue.put(event)
