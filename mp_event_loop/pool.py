import atexit
from .event_loop import EventLoop


__all__ = ['Pool']


class Pool(EventLoop):
    """Create multiple long running multiprocessing event loops."""

    def __init__(self, processes=1, output_handlers=None, event_queue=None, consumer_queue=None, name='main', has_results=True):
        """Create the event loop.

        Args:
            output_handlers (list/tuple/callable)[None]: Function or list of funcs that executed events with results.
            event_queue (Queue)[None]: Custom event queue for the event loop.
            consumer_queue (Queue)[None]: Custom consumer queue for the consumer process.
            name (str)['main']: Event loop name. This name is passed to the event process and consumer process.
            has_results (bool)[True]: Should this event loop create a consumer process to run executed events
                through process_output.
        """
        self.processes = processes
        self.loops = []
        super().__init__(output_handlers=output_handlers, event_queue=event_queue, consumer_queue=consumer_queue,
                         name=name, has_results=has_results)

    def start(self):
        """Start running the separate processes which runs an event loop."""
        self.stop()

        # Signal that the process is alive
        self.alive_event.set()

        # Create multiple processes
        for i in range(self.processes):
            el = EventLoop(name=self.name + '_' + str(i), has_results=False,
                           event_queue=self.event_queue, consumer_queue=self.consumer_queue)
            el.alive_event = self.alive_event
            el.start_event_loop()
            self.loops.append(el)

        # Consumer Thread
        if self.has_results:
            self.start_consumer_loop()

        self._needs_to_close = True
        atexit.register(self.stop)

    def stop(self):
        """Stop running the process.

        Warning:
            This will also stop the logging
        """
        if not self._needs_to_close:
            return

        super().stop()

        # Stop all of the event loops
        for loop in self.loops:
            loop.stop()
        self.loops = []

    def map(self, func, iter_args, iter_kwargs=None, cache=False):
        """Map each item (Event/arguments) in the iterator to run in a function in a separate process.

        See Also:
            add_event

        Args:
            func (callable): Function to call in a separate process.
            iter_args (iterable/list/tuple/iter): Iterator of positional arguments to pass into the function (add_event)
            iter_kwargs (iterable/list/tuple/iter): Iterator of dictionary keyword arguments
            cache (bool) [False]: If the target object should be cached
        """
        if iter_kwargs is None:
            iter_kwargs = [{}] * len(iter_args)

        for i, args in enumerate(iter_args):
            try:
                kwargs = iter_kwargs[i]
            except (IndexError, TypeError):
                kwargs = {}

            if 'cache' not in kwargs:
                kwargs['cache'] = cache
            try:
                iter(args)
                self.add_event(func, *args, **kwargs)
            except TypeError:
                self.add_event(func, args, **kwargs)

        self.wait()


