# mp_event_loop

Library for long running multiprocessing event loops.

This library provides an EventLoop that will run events in a separate process.

The EventLoop comes with several utilities for managing the separate process.

  * start() - Start the event loop
  * stop () - Stop the event loop
  * wait() - Wait for the current events to finish
  * run_until_complete(events=None) - Run the given events and wait until they are finished
  * is_running() - Return if the separate process is running
  * _\_enter_\_ and _\_exit_\_ - works as a context manager using the `with` statement    

The EventLoop also comes with some utilities to add commands to be processed and a way to handle results.

  * add_event(target, args, kwargs, ...) - Add an event to be executed in a separate process.
  * add_output_handler(function) - Function that takes in the event with results after the event has been executed.
    
These functions will be explained more below

## How it works
The EventLoop works by creating a Process and a Thread. The Process takes the 
Event from a queue and runs the function. Once the Event is complete and has a result the event is put on a result 
Queue. The Thread takes the Event from the result Queue and passes the event to all of the output_handlers in the 
EventLoop. If one of the output_handlers returns True the event will stop propagating to the other output_handlers.

Because of locking mechanisms in the Queue and message passing between processes this will be slow. You will probably 
only use this for concurrency. This is usefully for non-IO concurrency where Threads may impact performance.

I created this library as a test to understand how multiprocessing works. I am attempting to use multiprocessing for 
tcp communication and parsing data while passing the parsed data back to the main process which is running a GUI.
Concurrency and performance are vital for this GUI.

## Example

```python
import mp_event_loop

def add_one(value):
    return value + 1
    
    
results = []

def save_results(event):
    results.append(event.results)
    
with mp_event_loop.EventLoop(output_handlers=save_results) as loop:
    loop.add_event(add_one, args=(1,))
    loop.add_event(add_one, args=(2,))
    loop.add_event(add_one, args=(3,))
    
assert results == [2, 3, 4]
```  

## Events
Events simply take in a function and some arguments and execute them in a separate process. Theoretically, you could
make your own event for something specific.

```python
import mp_event_loop

class MyEvent(mp_event_loop.Event):
    def __init__(self, data, **kwargs):
        super().__init__(target=None, args=(data,), **kwargs)
        
    def run(self):
        data = self.args[0]
        
        # Run some calculation
        value = list(range(data))

        return value
        
    # def exec_(self):
    #     """Calls the run method and sets results or error."""
    #     # Get the command to run
    #     if callable(self.target):
    #         # Run the command
    #         try:
    #             self.results = self.run()
    #         except Exception as err:
    #             self.error = err
    #     else:
    #         self.error = ValueError("Invalid target (%s) given! Type %s" % (repr(self.target), str(type(self.target))))


def print_results(event):
    print(event.results)


loop = mp_event_loop.EventLoop()

loop.start()

loop.add_event(MyEvent(10))

loop.stop()

# At some point [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] should be printed
```

It is much easier to pass a function into an Event, but you may find this useful.


## Output Handlers

The EventLoop contains a list of output_handlers. An output handler is just a simple function that takes in an event.
The Event object will have results property which contains the results from the event execution

```python
import mp_event_loop

class MyEvent(mp_event_loop.Event):
    def __init__(self, data, **kwargs):
        super().__init__(target=None, args=(data,), **kwargs)
        
    def run(self):
        data = self.args[0]
        
        # Run some calculation
        value = list(range(data))

        return value
        
        
def print_my_event(event):
    if isinstance(event, MyEvent):
        print('My Event', event.results)
        return True  # Stop running the other output_handlers
    else:
        print("Not My Event")

def print_event(event):
    print("Normal Event", event.results)
    
    
def add_one(value):
    return value + 1
    
    
with mp_event_loop.EventLoop(output_handlers=[print_my_event, print_event]) as loop:
    loop.add_event(target=add_one, args=(1,))
    loop.add_event(target=add_one, args=(2,))
    loop.add_event(MyEvent(3))
    loop.add_event(target=add_one, args=(4,))
    loop.add_event(MyEvent(5))


# Not My Event
# Normal Event 2
# Not My Event
# Normal Event 3
# My Event [0, 1, 2]
# Not My Event
# Normal Event 5
# My Event [0, 1, 2, 3, 4]
```


## pickling
If pickling is annoying you then you can use a different multiprocessing library.

The EventLoop uses 4 class variables to create the proper Process and Thread objects

  * EventLoop.alive_event_class = multiprocessing.Event
  * EventLoop.queue_class = multiprocessing.JoinableQueue
  * EventLoop.event_loop_class = multiprocessing.Process
  * EventLoop.consumer_loop_class = threading.Thread

The `use` function has been provided to make this process easier.

```python
import mp_event_loop

import threading
import multiprocess as mp

mp_event_loop.use(mp)  # This does not change the consumer_loop_class
# mp_event_loop.use('multiprocess')  # Works for string arguments as well

# Or

# Below does the same as 'use'
mp_event_loop.EventLoop.alive_event_class = mp.Event
mp_event_loop.EventLoop.queue_class = mp.JoinableQueue
mp_event_loop.EventLoop.event_loop_class = mp.Process
mp_event_loop.EventLoop.consumer_loop_class = threading.Thread
```
