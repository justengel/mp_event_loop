import mp_event_loop
import multiprocessing_on_dill as mp

mp_event_loop.use(mp)
mp_event_loop.AsyncEventLoop.alive_event_class = mp.Event
mp_event_loop.AsyncEventLoop.queue_class = mp.JoinableQueue
mp_event_loop.AsyncEventLoop.event_loop_class = mp.Process


async def print_test(value, name):
    print(name)
    return value


def test_async_event_loop():

    results = []

    def save_results(event_results):
        results.append(event_results.results)

    with mp_event_loop.AsyncEventLoop(output_handlers=save_results) as loop:
        loop.add_event(print_test, args=(1, "hello"))
        # loop.add_event(print_test(1, "hello"))
        # loop.add_event(print_test(2, 'hi'))
        # loop.add_event(print_test(3, 'oi'))
        # loop.add_event(print_test(4, 'hey'))

    print(results)


if __name__ == '__main__':
    test_async_event_loop()
    print("All tests ran successfully!")
