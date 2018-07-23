import time

import mp_event_loop


class Point(object):
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self._z = z

    def get_x(self):
        return self.x

    def set_x(self, value):
        self.x = value

    def get_y(self):
        return self.y

    def set_y(self, value):
        self.y = value

    def move(self, x, y):
        self.x = x
        self.y = y

    def get_z(self):
        return self._z

    def set_z(self, z):
        self._z = z


class PointProxy(mp_event_loop.Proxy):
    # Pass the attributes down to the separate process
    PROXY_CLASS = Point
    PROPERTIES = ['x', 'y']
    GETTERS = ['get_x', 'get_y', 'get_z']

    def __init__(self, x=0, y=0, z=0, loop=None):
        super().__init__(loop=loop)
        self.x = x
        self.y = y
        self._z = z


def test_proxy():
    with mp_event_loop.EventLoop() as loop:
        p = PointProxy(loop=loop)
        p.move(1, 2)
        assert p.x == 0
        assert p.y == 0

    assert p.x == 1
    assert p.y == 2


def test_proxy_class_loop():
    with mp_event_loop.EventLoop() as loop:
        PointProxy.__loop__ = loop

        p = PointProxy()
        p.move(1, 2)
        assert p.x == 0
        assert p.y == 0

    assert p.x == 1
    assert p.y == 2


def test_proxy_alt_args():
    with mp_event_loop.EventLoop() as loop:
        p = PointProxy(2, 3, loop=loop)
        p.move(1, 2)
        assert p.x == 2
        assert p.y == 3

    assert p.x == 1
    assert p.y == 2


def test_proxy_wait():
    with mp_event_loop.EventLoop() as loop:
        p = PointProxy(2, 3, loop=loop)
        p.move(1, 2)
        t = time.clock()
        p.mp_wait()
        print("Wait time:", time.clock() - t)  # Slow!!!!! I'm in a GUI, so I don't really care
        assert p.x == 1
        assert p.y == 2

    assert p.x == 1
    assert p.y == 2


def test_proxy_getter_property_conflict():
    """Show the difference between GETTER and PROPERTY. If you don't sync both there could be differing results."""
    with mp_event_loop.EventLoop() as loop:
        PointProxy.__loop__ = loop

        p = PointProxy()
        assert p._z == 0
        assert p.get_z() is None

        p.set_z(3)
        assert p._z == 0
        assert p.get_z() is None

    assert p._z == 0
    assert p.get_z() == 3


if __name__ == '__main__':
    test_proxy()
    test_proxy_class_loop()
    test_proxy_alt_args()
    test_proxy_wait()
    test_proxy_getter_property_conflict()
    print("All tests ran successfully!")
