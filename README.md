# mp_event_loop

Library for long running multiprocessing event loops. This library provides an EventLoop that will run events in a 
separate process.


    Warning:
    This library does not work with async/await.
    Coroutines and generators cannot be pickled which prevents them from being run in a separate process.


The EventLoop comes with several utilities for managing the separate process.

  * is_running() - Return if the separate process is running
  * start() - Start the event loop
  * run(events=None, output_handlers=None) - Add the output handlers and run the events
  * run_until_complete(events=None, output_handlers=None) - Run the given events and wait until they are finished
  * wait() - Wait for the current events to finish
  * stop() - Stop the event loop
  * close() - Close the event loop
  * _\_enter_\_ and _\_exit_\_ - works as a context manager and allows use of the `with` statement    

The EventLoop also comes with some utilities to add commands to be processed and a way to handle results.

  * add_event(target, args, kwargs, ...) - Add an event to be executed in a separate process.
  * add_output_handler(function) - Function that takes in an EventResult after the event has been executed.
    
These functions will be explained more below


## Quickstart

    pip install mp_event_loop
    
```python
import mp_event_loop


def add_vals(value, value2=1):
    return value + value2
    
    
results = []

def save_results(event_result):
    results.append(event_result.results)


with mp_event_loop.get_event_loop(output_handlers=save_results):
    mp_event_loop.add_event(add_vals, 2)
    mp_event_loop.add_event(add_vals, 3, 4)
    mp_event_loop.add_event(add_vals, 5, value2=6)
    mp_event_loop.add_event(add_vals, args=(7,), kwargs={'value2': 8})
    
# with context manager waits for events and event results to finish until it exits
assert results == [3, 7, 11, 15]
summed = sum(results)
assert summed == 36
print("Results summed:", summed)
# Results summed: 36
```

Alternative approach
```python
import mp_event_loop as mp_event_loop

def add_one(value):
    return value + 1
    
    
results = []

def save_results(event_result):
    results.append(event_result.results)
    
mp_event_loop.run([{'target': add_one, 'args': (1,)},
                   {'target': add_one, 'args': (2,)},
                   {'target': add_one, 'args': (3,)},
                  ], save_results)
                  
mp_event_loop.add_event(add_one, 4)

mp_event_loop.wait()

print("Results summed:", sum(results))
# Results summed: 14
```

## How it works
The EventLoop works by creating a Process and a Thread. The Process takes the 
Event from a queue and runs the function. Once the Event is complete, an EventResult is put on a result Queue. 
The Thread takes the EventResult from the result Queue and passes it to all of the output_handlers in the EventLoop. 
If one of the output_handlers returns True the event result will stop propagating to the other output_handlers.

Because of locking mechanisms in the Queue and message passing between processes this will be slow. You will probably 
only use this for concurrency. This is usefully for non-IO concurrency where Threads may impact performance.

I created this library as a test to understand how multiprocessing works. I am attempting to use multiprocessing for 
tcp communication and parsing data. I want the parsing to happen in a separate process, but I want to access the 
parsed data in a thread allowing a GUI to run. Concurrency and performance is vital for this GUI.

## Example

```python
import mp_event_loop

def add_one(value):
    return value + 1
    
    
results = []

def save_results(event_result):
    results.append(event_result.results)
    
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


def print_results(event_result):
    print(event_result.results)


loop = mp_event_loop.EventLoop(output_handlers=print_results)

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
        
        
def print_my_event(event_result):
    if isinstance(event_result.event, MyEvent):
        print('My Event', event_result.results)
        return True  # Stop running the other output_handlers
    else:
        print("Not My Event")

def print_event(event_result):
    print("Normal Event", event_result.results)
    
    
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


## Pickling
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

### Pickling Problems
My goal was to extend this library to work with async/await. Unfortunately, coroutines and generators cannot be 
pickled. I created an async_event_loop.AsyncEventLoop just in case this becomes possible in the future. 

In addition to this generators cannot be pickled. I wanted to create another event loop where function with the yield
statement would allow other Events to run. While generators cannot be pickled, it is possible to create a class with
 _\_iter_\_ and _\_next_\_ methods which can be pickled. I created an event loop (iter_event_loop.IterEventLoop)
which will collect iterators and interleave iterators. After _\_next_\_ is called a different iterator will execute 
adding more concurrency. This only makes it so long running iterators do not take up all of the processing time and 
lets other iterator events run in between iterations.
