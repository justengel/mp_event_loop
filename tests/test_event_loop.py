import multiprocessing as mp
import mp_event_loop


def plus_one(value):
    return value + 1


def return_print(value):
    print(value)
    return value


def test_concurrency():
    records = [None] * 200 * 3
    record_idx = [0]

    out_queue = mp.JoinableQueue()

    def save_record(event):
        records[record_idx[0]] = event.results
        record_idx[0] += 1

    with mp_event_loop.EventLoop("EL 1", consumer_queue=out_queue, output_handlers=save_record) as el1,\
            mp_event_loop.EventLoop('EL two', consumer_queue=out_queue, has_results=False) as el2,\
            mp_event_loop.EventLoop('EL three', consumer_queue=out_queue, has_results=False) as el3:

        # Fast iterator to quickly add all of the events.
        all((el1.add_event(return_print, args=('EL 1\t%d' % i,)),
             el2.add_event(return_print, args=('EL two\t%d' % i,)),
             el3.add_event(return_print, args=('EL three\t%d' % i,)))
            for i in range(200))

        print('exit the context')

    # Make sure all of the items did not get processed on after the other.
    assert ['EL 1\t%d' % i for i in range(200)] not in records
    assert ['EL two\t%d' % i for i in range(200)] not in records
    assert ['EL three\t%d' % i for i in range(200)] not in records
    print("Success! The event loops worked concurrently")


def test_event_loop():
    CACHE = True
    records = []

    def save_record(event):
        records.append(event.results)

    el = mp_event_loop.EventLoop()
    el.add_output_handler(save_record)

    el.start()

    el.add_event(plus_one, args=(1,), cache=CACHE)
    el.add_event(plus_one, args=(2,), cache=CACHE)
    el.add_event(plus_one, args=(3,), cache=CACHE)
    el.add_event(plus_one, args=(4,), cache=CACHE)
    el.add_event(plus_one, args=(5,), cache=CACHE)
    el.add_event(plus_one, args=(6,), cache=CACHE)

    any((el.add_event(plus_one, args=(i,), cache=CACHE)) for i in range(200))

    el.wait()
    el.stop()

    index = 0
    for expected in range(2, 8):
        try:
            assert records[index] == expected
        except IndexError as err:
            raise IndexError("Index " + repr(index) + " does not exist") from err
        index += 1
    for expected in range(1, 201):
        try:
            assert records[index] == expected
        except IndexError as err:
            raise IndexError("Index " + repr(index) + " does not exist") from err
        index += 1


if __name__ == '__main__':
    import timeit

    # mp_event_loop.use('multiprocess')
    # mp_event_loop.use('multiprocessing')

    test_concurrency()
    # test_event_loop()

    # tm = timeit.timeit(test_event_loop, number=20)
    # print(tm)
    #
    # tm = timeit.timeit(test_event_loop, number=20)
    # print(tm)

    print("All tests ran successfully!")