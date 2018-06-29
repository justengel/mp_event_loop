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
  * add_output_handler(function) - Function that takes in an Event after the event has been executed.
    
These functions will be explained more below


## Quickstart

    pip install mp_event_loop
    
```python
import mp_event_loop


def add_vals(value, value2=1):
    return value + value2
    
    
results = []

def save_results(event):
    results.append(event.results)


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

def save_results(event):
    results.append(event.results)
    
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
Event from a queue and runs the function. Once the Event is complete, the event is put on a result Queue/consumer Queue. 
The Thread takes the Event from the result Queue and passes it to all of the output_handlers in the EventLoop. 
If one of the output_handlers returns True the event will stop propagating to the other output_handlers.

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
    #     """Get the command and run it"""
    #     # Get the command to run
    #     self.results = None
    #     self.error = None
    #     if callable(self.target):
    #         # Run the command
    #         try:
    #             self.results = self.run()
    #         except Exception as err:
    #             self.error = err
    #     elif self.target is not None:
    #         self.error = ValueError("Invalid target (%s) given! Type %s" % (repr(self.target), str(type(self.target))))


def print_results(event):
    print(event.results)


loop = mp_event_loop.EventLoop(output_handlers=print_results)

loop.start()

loop.add_event(MyEvent(10))

loop.stop()

# At some point [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] should be printed
```

It is much easier to pass a function into an Event, but you may find this useful.


## Output Handlers

The EventLoop contains a list of output_handlers. An output handler is just a simple function that takes in an event.
The Event object will have results property which contains the results from the event execution (results return 
from the target function).

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

## Object State
One thing to remember is that objects in the other process will have a different state than objects in the main process.

This can be seen with the code below.

```python
import mp_event_loop


class ABC(object):
    def __init__(self, a, b, c):
        self.a = a
        self.b = b
        self.c = c

    def calc_c(self):
        self.c = self.a + self.b

    def __repr__(self):
        return "ABC(a=%d, b=%d, c=%d)" % (self.a, self.b, self.c)
        

a = ABC(1, 2, 0)

with mp_event_loop.get_event_loop(has_results=False) as loop:
    loop.add_event(print, "=====", a, "=====")  # Prints a correctly "ABC(a=1, b=2, c=0)"
    loop.add_event(a.calc_c)  # Does calculation, but doesn't send the result back to us
    # The other process has the correct c value but never passes it back

    # We are passing this a's values down which is 1, 2, 0. We never got the result of "a.calc_c()"
    loop.add_event(print, a)   # Prints the 'a' that the main thread passed to the process "ABC(a=1, b=2, c=0)"
```

This example shows that `a` in the main process is never changing. `a.calc_c()` is run the other process, but the 
other process does not save the object `a`. In the scope of the other process `a` with `a.calc_c()` dies and goes away.
The main process `a` never changed and still has the values of a=1, b=2, c=0.

To solve this problem I created some caching events. These events save object with an id. The other process is given 
the object_id and uses it to get the correct object.

```python
a = ABC(1, 2, 0)

with mp_event_loop.get_event_loop(has_results=False) as loop:
    loop.add_event(print, "=====", a, "=====")  # Prints a correctly "ABC(a=1, b=2, c=0)"
    
    # You can manually cache an object
    # loop.cache_object(a)
    # Only needed for object arguments 'loop.add_event(my_func, a, cache=True)' only my_func is registered and cached.
    # If 'a' is cached it will use it by using a's object_id, but it will not register and cache the 'a' object.  
    
    # Or pass in cache=True or loop.add_cache_event
    loop.add_event(a.calc_c, cache=True)  # Keeps track of an id for 'a' and saves 'a' in the separate process
    
    # DO NOT pass a down to the other process. Instead pass an object_id for 'a'. The other process will use the 
    # object_id to get the stored 'a' object and use that object.
    loop.add_event(print, a, cache=True)  # Prints the cached 'a' object correctly "ABC(a=1, b=2, c=3)"
```

### Object State - passing the object back to the main process
While caching the object in the other process may be useful it is still limited. The biggest drawback is that the main
process does not have the correct object values. If you want the objects to keep the correct state it is advised to use
the multiprocessing shared memory.

If shared memory is not your desire and you don't need the result immediately, you can use the mp_event_loop as a 
form of message passing to maintain an object's state.

```python
import mp_event_loop

a = ABC(1, 2, 0)


def save_object(event):
    if event.event_key == 'a':
        a.a = event.results.a
        a.b = event.results.b
        a.c = event.results.c
        return True


with mp_event_loop.get_event_loop(output_handlers=save_object) as loop:
    loop.add_event(print, "=====", a, "=====")  # Prints a correctly "ABC(a=1, b=2, c=0)"
    loop.add_event(a.calc_c)  # Does calculation, but doesn't send the result back to us
    # The other process has the correct c value but never passes it back

    # We are passing this a's values down which is 1, 2, 0. We never got the result of "a.calc_c()"
    loop.add_event(print, "No cache", a)
    
    # Use caching events
    loop.add_event(a.calc_c, cache=True)
    loop.add_event(print, "Cached", a, cache=True)

    # Try getting the object back with save_result_object
    loop.cache_object(a, has_output=True, event_key='a')  # has_output=True sends the event back into the consumer queue
    print("Main process", a)
    loop.add_event(print, "No cache", a)  # This fails, because the event has not run and come back yet.
    loop.add_event(print, "Cached", a, cache=True)

print("Main process after event loop", a)
```

The output of the above code looks like

    Main process ABC(a=1, b=2, c=0)
    ===== ABC(a=1, b=2, c=0) =====
    No cache ABC(a=1, b=2, c=0)
    Cached ABC(a=1, b=2, c=3)
    No cache ABC(a=1, b=2, c=0)
    Cached ABC(a=1, b=2, c=3)
    Main process after event loop ABC(a=1, b=2, c=3)
    
    Process finished with exit code 0
    
Take note that the first thing printed is `Main process ABC(a=1, b=2, c=0)`. Even though the print statement is near 
the end of the with statement this is the first thing printed. All of the events are thrown on a queue and are executed
in a separate process later. You have to wait until after all of the events are processed to get the correct results.
`Main process after event loop ABC(a=1, b=2, c=3)` is correct, because it is outside of the with statement and waits 
until all events are complete.

I hope you read all that carefully and fully understand how it works before you use it. Enjoy.

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
