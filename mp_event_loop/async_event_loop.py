import types

from .events import EventResults, Event, CacheEvent
from .event_loop import EventLoop
from .mp_functions import mark_task_done, LoopQueueSize


__all__ = ['run_async_event_loop', 'AsyncEventLoop']


def run_async_event_loop(alive_event, event_queue, consumer_queue=None):
    """Run the event loop.

    Args:
        alive_event (multiprocessing.Event): Event to signal when to end the thread
        event_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to get and run events with
        consumer_queue (multiprocessing.Queue/multiprocessing.JoinableQueue): Queue to pass results from the process
            to the thread.
    """
    async_generator_events = []
    # ===== Run the logging event loop =====
    for _ in LoopQueueSize(alive_event, event_queue):
        if len(async_generator_events) == 0 or not event_queue.empty():
            # Get an event an run it
            event = event_queue.get()

            if isinstance(event, Event):
                # Run the event
                event_results = event.exec_()
                if event_results.results and isinstance(event_results.results, types.CoroutineType):
                    try:
                        event_results.results = event_results.results.send(None)  # The coroutine is finally called
                    except StopIteration:
                        pass
                elif event_results.results and isinstance(event_results.results, types.AsyncGeneratorType):
                    event.async_generator = event_results.results
                    async_generator_events.append(event)
                    event_results = None

                if event.has_output and event_results is not None:
                    consumer_queue.put(event_results)

            mark_task_done(event_queue)

        # Loop through the existing async_generators
        offset = 0
        for i in range(len(async_generator_events)):
            event = None
            event_results = EventResults()
            try:
                event = async_generator_events[i + offset]
                event_results.event = event
                event_results.event_key = event.event_key

                coro = event.async_generator.asend(None)
                event_results.results = coro.send(None)
            except StopIteration:
                # Every coro.send call will cause a StopIteration
                pass
            except (StopAsyncIteration, AttributeError):
                # The async generator is complete
                async_generator_events.pop(i)
                offset -= 1
                continue
            except Exception as err:
                event_results.error = err

            # Put the results on the queue
            if event is not None and event.has_output and event_results is not None:
                consumer_queue.put(event_results)

    alive_event.clear()


class AsyncEventMixin(object):
    def run(self):
        """Run the actual command that was given and return the results"""
        if isinstance(self.target, types.CoroutineType):
            try:
                return self.target.send(None)
            except StopIteration:
                pass
        elif isinstance(self.target, types.AsyncGeneratorType):
            return self.target
        else:
            return self.target(*self.args, **self.kwargs)


class AsyncEvent(AsyncEventMixin, Event):
    pass


class AsyncCacheEvent(AsyncEventMixin, CacheEvent):
    pass


class AsyncEventLoop(EventLoop):
    """EventLoop to work with async/await coroutines."""
    run_event_loop = staticmethod(run_async_event_loop)

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
            event = AsyncCacheEvent(target, *args, **kwargs, has_output=has_output, event_key=event_key,
                                    re_register=re_register, cache=self.cache)

        elif isinstance(target, Event):
            event = target
        else:
            if has_output is None:
                has_output = True
            event = AsyncEvent(target, *args, **kwargs, has_output=has_output, event_key=event_key)

        self.event_queue.put(event)
