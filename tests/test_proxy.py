import mp_event_loop


class MpPoint(mp_event_loop.MpProxy):
    # Pass the attributes down to the separate process
    MP_METHODS = [mp_event_loop.MpMethod('get_z', 'set_z')]
    MP_ATTRIBUTES = [mp_event_loop.MpAttribute('x'), mp_event_loop.MpAttribute('y')]

    def __init__(self, x=0, y=0, z=0, loop=None):
        self.x = x
        self.y = y
        self._z = z

        super().__init__(loop=loop)

    def get_z(self):
        return self._z

    def set_z(self, z):
        self._z = z

    # Run the function in a separate process and get the results back.
    @mp_event_loop.proxy_func(properties=['x', 'y', '_z'])
    def move(self, x, y, z):
        self.x = x
        self.y = y
        self._z = z


def test_proxy():
    with mp_event_loop.EventLoop() as loop:
        p = MpPoint(loop=loop)
        p.move(1, 2, 3)
        assert p.x == 0
        assert p.y == 0
        assert p._z == 0
        assert p.get_z() == 0

    assert p.x == 1
    assert p.y == 2
    assert p._z == 3
    assert p.get_z() == 3


if __name__ == '__main__':
    test_proxy()
