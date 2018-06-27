import multiprocessing as mp
import mp_event_loop
from mp_event_loop.iter_event_loop import IterEventLoop


def my_gen(name, value):
    for i in range(value):
        print(name, i)
        yield i


class MyIter(object):
    """Iterator form of my_gen"""
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.index = value

    def __iter__(self):
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        val = self.index
        self.index -= 1
        if self.index <= -1:
            raise StopIteration
        print(self.name, val)
        return val


def test_iterator():
    records = [None] * 200 * 3 * 200 * 3
    record_idx = [0]

    out_queue = mp.JoinableQueue()

    def save_record(event):
        records[record_idx[0]] = event.results
        record_idx[0] += 1

    with IterEventLoop("EL 1", consumer_queue=out_queue, output_handlers=save_record) as el1,\
            IterEventLoop('EL two', consumer_queue=out_queue, has_results=False) as el2,\
            IterEventLoop('EL three', consumer_queue=out_queue, has_results=False) as el3:

        # Fast iterator to quickly add all of the events.
        all((el1.add_event(MyIter('EL 1 - %d iter' % i, 20)),
             el2.add_event(MyIter('EL two - %d iter' % i, 20)),
             el3.add_event(MyIter, args=('EL three - %d iter' % i, 20)),
             )
            for i in range(5))

        print('exit the context')

    # Make sure all of the items did not get processed on after the other.
    # assert ['EL 1\t%d' % i for i in range(200)] not in records
    # assert ['EL two\t%d' % i for i in range(200)] not in records
    # assert ['EL three\t%d' % i for i in range(200)] not in records
    print("Success! The event loops worked concurrently")


def test_generators():
    records = [None] * 200 * 3 * 200 * 3
    record_idx = [0]

    out_queue = mp.JoinableQueue()

    def save_record(event):
        records[record_idx[0]] = event.results
        record_idx[0] += 1

    with IterEventLoop("EL 1", consumer_queue=out_queue, output_handlers=save_record) as el1,\
            IterEventLoop('EL two', consumer_queue=out_queue, has_results=False) as el2,\
            IterEventLoop('EL three', consumer_queue=out_queue, has_results=False) as el3:

        # Fast iterator to quickly add all of the events.
        all((el1.add_event(iter(my_gen('EL 1 - %d iter' % i, 20))),
             el2.add_event(my_gen('EL two - %d iter' % i, 20)),
             # el3.add_event(my, args=('EL three - %d iter' % i, 20)),
             )
            for i in range(5))

        print('exit the context')

    # Make sure all of the items did not get processed on after the other.
    # assert ['EL 1\t%d' % i for i in range(200)] not in records
    # assert ['EL two\t%d' % i for i in range(200)] not in records
    # assert ['EL three\t%d' % i for i in range(200)] not in records
    print("Success! The event loops worked concurrently")


if __name__ == '__main__':
    test_iterator()
    # test_generators()  # Generators cannot be pickled

    print("All tests ran successfully!")
