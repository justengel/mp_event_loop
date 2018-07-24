"""
Note:
    Coroutines cannot be pickled ... A multiprocessing approach to coroutines may not be possible.
"""

import types

# http://www.dabeaz.com/coroutines/Coroutines.pdf
# The above slides help a lot!


# ========== Test basic async ==========
async def print_test():
    print("what is this? How do I call it?")
    return 2


print(print_test)
print(type(print_test))
print("is coroutine?", isinstance(print_test, types.CoroutineType))
print(dir(print_test))
# print_test()  # Causes error ... RuntimeWarning: coroutine 'blah' was never awaited
# await print_test()  # Causes error await only allowed in async? ... SyntaxError: invalid syntax
something = print_test()  # This is the coroutine ...
print(something)
print("is coroutine?", isinstance(something, types.CoroutineType))
try:
    value = something.send(None)  # The coroutine is finally called or next
    print(value)
except StopIteration:
    pass


# ========== Test yield in async ==========
async def print_test2(num=3):
    for i in range(num):
        print("here", i)
        yield i


something2 = print_test2()
print(something2)
print("is coroutine?", isinstance(something2, types.CoroutineType))
print("is async generator?", isinstance(something2, types.AsyncGeneratorType))
# Causes error ... Because of yield this is not a coroutine anymore ... Why? Oh it is an async_generator ... ... ...
# try:
#     something2.send(None)  # The coroutine is finally called
# except StopIteration:
#     pass

# Causes error ... TypeError: 'async_generator' object is not iterable
# for item in something2:
#     print(item)

# Causes error ... Async generator cannot be used in this way? Async generator can only be used in an async def function
# async for item in something2:
#     print(item)

another_thing = something2.asend(None)  # This does nothing
print(another_thing)
print("is coroutine?", isinstance(another_thing, types.CoroutineType))
print("is async generator?", isinstance(another_thing, types.AsyncGeneratorType))
print(type(another_thing))
# another_thing()  # Causes error ... Not callable
# another_thing.send(None)  # AttributeError
# another_thing.asend(None)  # AttributeError

# OMG it runs!!! - here 0 was printed ...
for i in another_thing:
    pass
    # print(i)

another_thing2 = something2.asend(None)
another_thing3 = something2.asend(None)
another_thing4 = something2.asend(None)
another_thing5 = something2.asend(None)


try:
    another_thing2.send(None)
except StopIteration:
    pass  # Hits here

try:
    next(another_thing3)
except StopIteration:
    pass  # Hits here

try:
    next(another_thing4)
except StopIteration:
    pass
except StopAsyncIteration:
    pass  # Hits here

# try:
#     next(another_thing5)
# except StopAsyncIteration:
#     pass  # Hits here


# ========== Test await in async ==========
print("========== Test 3 ==========")
async def print_test3(num=3):
    # What do I even put here? This is basically a JoinableQueue join right?
    # __await__() needs an iterator can I use an async generator here?
    # await print_test2(num)
    # await range(1)  # Generator doesn't work
    # await iter(range(1))  # Iterator doesn't work either.

    # class Wait(object):
    #     def __await__(self):
    #         return iter(range(1))
    # await Wait()  # waits forever. Something must have to happen with the iterator

    class Wait(object):
        def __await__(self):
            return iter(range(0))
    await Wait()

    print('waited')


something3 = print_test3()
print(something3)

try:
    something3.send(None)  # The coroutine is finally called
except StopIteration:
    pass


print("This seems abnormally complex and is not intuitive.\n"
      "You are also really designing for this framework which is annoying...\n"
      "I'm going to try to make an async event loop to work with this.")

print("Maybe this can be run with a new simple event.")
