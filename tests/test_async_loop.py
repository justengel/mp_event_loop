import mp_event_loop
from mp_event_loop.async_event_loop import AsyncEventLoop, AsyncManager


async def print_test(value, name):
    print("Print", name)
    return value


async def yield_range(value, name):
    print("Yield", name)
    for i in range(value):
        yield name + " " + str(i)


AsyncManager.register('print_test', print_test)
AsyncManager.register('yield_range', yield_range)


def test_async_event_loop():

    results = []

    def save_results(event):
        results.append(event.results)

    with AsyncEventLoop(output_handlers=save_results) as loop:
        loop.async_event(print_test, 1, "hello")
        loop.async_event(print_test, 2, "hi")
        loop.async_event(print_test, 3, "oi")
        loop.async_event(yield_range, 5, 'first')
        loop.async_event(yield_range, 5, 'second')

    assert results[:3] == [1, 2, 3], results

    excpected = ['first ' + str(i) for i in range(5)] + ['second ' + str(i) for i in range(5)]
    for exp in excpected:
        assert exp in results, '%s not in the results list' % exp

    print(results)


if __name__ == '__main__':
    test_async_event_loop()
    print("All tests ran successfully!")
