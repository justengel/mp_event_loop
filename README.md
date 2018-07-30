# mp_event_loop

Library for long running multiprocessing event loops. This library provides an EventLoop that will run events in a 
separate process. The purpose of this library is to manage a long running process while a GUI is running in the main 
thread. Tasks can be offloaded to another processes continuously while the GUI is running. 

**Now works with async/await!** see the example below.

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


## Quick Start

    pip install mp_event_loop
    
```python
import mp_event_loop


def add_vals(value, value2=1):
    return value + value2
    
    
results = []

def save_results(event):
    results.append(event.results)


with mp_event_loop.get_event_loop(save_results):
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
import mp_event_loop

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
## Async / Await

You must register your coroutines with the AsyncManager in order to run in a separate process. Coroutines are not 
picklable, so they must be registered at the module level. During unpickling (_\_setstate_\_) the coroutine will be 
retrieved by the registered name using the AsyncManager.


```python
from mp_event_loop import AsyncEventLoop, AsyncManager


async def print_test(value, name):
    print("Print", name)
    return value


async def yield_range(value, name):
    print("Yield", name)
    for i in range(value):
        yield name + " " + str(i)


# Do not need to register anymore
# AsyncManager.register('print_test', print_test)
# AsyncManager.register('yield_range', yield_range)


if __name__ == '__main__':
    results = []

    def save_results(event):
        results.append(event.results)

    with AsyncEventLoop(output_handlers=save_results) as loop:
        loop.async_event(print_test, 1, "hello")
        loop.async_event(print_test, 2, "hi")
        loop.async_event('print_test', 3, "oi")  # Can also use the registered name
        loop.async_event(yield_range, 5, 'first')
        loop.async_event(yield_range, 5, 'second')

    print(results)
    # [1, 2, 3, 'first 0', 'first 1', 'second 0', 'first 2', 'second 1', 'first 3', 'second 2', 'first 4', 'second 3', 'second 4']

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
parsed data in a thread allowing a GUI to run.


## Object Persistence
The overall goal for this library is a long running process where tasks can run easily. Along with this is object 
persistence. You can easily send an object to a separate process and run a task on it. The difficult part is getting
the values from that object back. The multiprocessing library already as a good way of doing this through the Manager 
class. However, I found this approach difficult to use with PySide.

```python
# example problem
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
    # The other process has the correct c value but never passes it back to the correct object

    # We are passing this a's values down which is 1, 2, 0. We never got the result of "a.calc_c()"
    loop.add_event(print, a)   # Prints the 'a' that the main thread passed to the process "ABC(a=1, b=2, c=0)"
```

This library tries to solve this problem in two ways.

The first way I label as caching. The CacheEvent solves this by saving a reference to an object in a dictionary. 
The object is pickled to a separate process one time and saved. Every subsequent CacheEvent uses a key (id) to 
retrieve the cached object and run in the other process with that cached object

The second way is through a proxy where an object only exists in the other process. My approach to a proxy has the 
main process keep a reference to a simple object. When that object is pickled it creates an object in the other 
process. It creates this object once then uses caching to save a reference to that object. The object only lives in 
the other process. You can controll the object by calling function in the main process which really just sends an 
event to run on the other process. If you want an attribute value or getter method value exposed on the main process 
then you need to define `PROPERTIES` and `GETTERS`. Note: this is merely a solution I found to work with PySide and 
creating widgets dynamically in another process. I plan on having another library named qt_concurrency to handle the 
specifics between long running multiprocessing and Qt.


### CacheEvent
The above example shows that `a` in the main process is never changing. `a.calc_c()` is run the other process, but the 
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

While this now works like we want it to there is still a problem. `a` in the main process does not have the correct 
values. You can solve this with tedious event handling shown below.

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
    loop.add_event(a.calc_c)  # Does calculation and sends the event back through the output_handler
    # However we have no way of identifying what event/object was returned back to us (in save_object)
    
    # Try getting the object back with save_result_object
    loop.add_event(a.calc_c, event_key='a')  # We can use the event_key to identify the returned event (in save_object)
    print("Main process", a)  # The multiprocessing has not happened yet. No immediate results.

print("Main process after event loop", a)  # The loop has now waited for all tasks to complete and results are correct.
```

### Proxy object
This is by far the most challenging part of this library. For my application I don't care about immediate results. I 
care about concurrency and long running tasks being done in a separate process allowing a GUI to live.

Below is example code for a Proxy. The proxy object only has access to 

```python
import mp_event_loop

class Point(object):
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self._z = z
        
    def get_z(self):
        return self._z
        
    def set_z(self, z):
        self._z = z

    def move(self, x, y, z):
        self.x = x
        self.y = y
        self._z = z
        
class MpPoint(mp_event_loop.Proxy):
    PROXY_CLASS = Point
    PROPERTIES = ['x', 'y']
    GETTERS = ['get_z']

    def __init__(self, x=0, y=0, z=0, loop=None):
        super().__init__(loop=loop)
        self.x = x
        self.y = y
        self._z = z
    


with mp_event_loop.EventLoop() as loop:
    p = MpPoint(loop=loop)
    p.set_z(3)  # Runs in the other process
    assert p._z != 3 
    assert p.get_z() != 3
    
    # Sends object down to separate process and runs move.
    # The separate process has attributes x and y and uses get_z and set_z to have the correct z value.
    p.move(1, 2, 7)
    assert p.x == 0
    assert p.y == 0
    assert p._z == 3
    assert p.get_z() == 3

assert p.x == 1
assert p.y == 2
assert p.get_z() == 7
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
pickled. 

Initially the async/await event loop failed because generators cannot be pickled. I wanted to create another event 
loop where function with the yield statement would allow other Events to run. While generators cannot be pickled, 
it is possible to create a class with  _\_iter_\_ and _\_next_\_ methods which can be pickled. I created an event 
loop (iter_event_loop.IterEventLoop) which will collect iterators and interleave iterators. After _\_next_\_ is called 
a different iterator will execute adding more concurrency. This only makes it so long running iterators do not take 
up all of the processing time and lets other iterator events run in between iterations.

I was able to get async/await to work in multiprocessing. I used the same technique that I used for caching which was
to register the async functions in a class dictionary and pickle the registered name. At unpickling the registered name
is used to retrieve the async function and run it in the other process.
