"""
This test shows the same thing that the Proxy is doing. The Proxy creates an object in a separate process then sends
function calls to that object. The Proxy object only has values for the set PROPERTIES and GETTERS.
"""
import mp_event_loop
from var_event import VarEventLoop, VarEvent


class Point(object):
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def move(self, x, y):
        self.x = x
        self.y = y
        print('Move', self.x, self.y)


def create_point():
    p = Point(1, 1)
    return {'p': p}


def test_initialize_process():
    results = []

    def save_results(event):
        results.append(event.results)

    with VarEventLoop(output_handlers=save_results, initialize_process=create_point) as loop:
        loop.add_var_event('p', 'move', 2, 3)
        loop.wait()


class PointProxy(mp_event_loop.Proxy):
    PROXY_CLASS = Point
    PROPERTIES = ['x', 'y']


def test_proxy():
    results = []

    def save_results(event):
        results.append(event.results)

    with mp_event_loop.EventLoop() as loop:
        PointProxy.__loop__ = loop

        p = PointProxy(1, 1)
        p.move(2, 3)
        assert p.x != 2
        assert p.y != 3

    assert p.x == 2
    assert p.y == 3


if __name__ == '__main__':
    test_initialize_process()
    test_proxy()
    print("All tests ran successfully!")
