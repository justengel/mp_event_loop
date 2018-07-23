import mp_event_loop


def get_proc(a, b):
    return a + b


def test_pool():
    results = []

    def save_results(event):
        results.append(event.results)

    with mp_event_loop.Pool(4, output_handlers=save_results) as pool:
        pool.add_event(get_proc, 1, 2)
        pool.add_event(get_proc, 3, 4)
        pool.add_event(get_proc, 5, 6)
        pool.add_event(get_proc, 7 ,8)
        assert len(results) != 4

    assert len(results) == 4, results
    assert 3 in results
    assert 7 in results
    assert 11 in results
    assert 15 in results
    print("Pool results", results, 'Results are unlikely to be in the same order [3, 7, 11, 15].')


def test_pool_map():
    results = []

    def save_results(event):
        results.append(event.results)

    with mp_event_loop.Pool(processes=4, output_handlers=save_results) as pool:
        pool.map(get_proc, [(1, 2), (3, 4), (5, 6), (7, 8)])
        assert len(results) == 4
        assert 3 in results
        assert 7 in results
        assert 11 in results
        assert 15 in results
        print("Map results", results, 'Results are unlikely to be in the same order [3, 7, 11, 15].')

    # print("Pool stopped")


class MpPoint(mp_event_loop.Proxy):
    # Pass the attributes down to the separate process
    PROPERTIES = ['x', 'y']
    GETTERS = ['get_z']

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
    def move(self, x, y, z):
        self.x = x
        self.y = y
        self._z = z
        return self


def test_pool_cache():
    results = []

    def save_results(event):
        results.append(event.results)

    with mp_event_loop.Pool(4, output_handlers=save_results) as pool:
        p = MpPoint(loop=pool)
        p.move(1, 2, 3)

        pool.map(p.move, [
            (1, 2, 3),
            (4, 5, 6),
            (7, 8, 9),
            (10, 11, 12)
            ])
        assert p.x == 0
        assert p.y == 0
        assert p._z == 0
        assert p.get_z() == 0


if __name__ == '__main__':
    test_pool()
    test_pool_map()
    test_pool_cache()
    print("All tests passed successfully!")
