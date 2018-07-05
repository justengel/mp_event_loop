import mp_event_loop


class MpPoint(mp_event_loop.MpProxy):
    MP_ATTRIBUTES = [mp_event_loop.MpAttribute('x'), mp_event_loop.MpAttribute('y')]

    def __init__(self, x=0, y=0, loop=None):
        self.x = x
        self.y = y

        super().__init__(loop=loop)

    @mp_event_loop.proxy_func(properties=['x', 'y'])
    def move(self, x, y):
        self.x = x
        self.y = y


def test_proxy():
    with mp_event_loop.EventLoop() as loop:
        p = MpPoint(loop=loop)
        p.move(1, 2)
        assert p.x == 0
        assert p.y == 0

    assert p.x == 1
    assert p.y == 2


if __name__ == '__main__':
    test_proxy()
