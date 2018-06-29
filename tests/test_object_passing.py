"""
Check how objects with continuous operations work.
"""

import mp_event_loop


class ABC(object):
    def __init__(self, a, b, c):
        self.a = a
        self.b = b
        self.c = c

    def calc_c(self):
        self.c = self.a + self.b

    def __repr__(self):
        return "ABC(a=%d, b=%d, c=%d)" % (self.a, self.b, self.c)


def test_object_state():
    # with mp_event_loop.get_event_loop() as loop:
    #     loop.add_event(print, 'hello world!')
    #     loop.add_event(exec, "x = 1\ny = x * 3\nprint(x, y)")

    a = ABC(1, 2, 0)

    with mp_event_loop.get_event_loop(has_results=False) as loop:
        loop.add_event(print, "=====", a, "=====")  # Prints a correctly "ABC(a=1, b=2, c=0)"
        loop.add_event(a.calc_c)  # Does calculation, but doesn't send the result back to us
        # The other process has the correct c value but never passes it back

        # We are passing this a's values down which is 1, 2, 0. We never got the result of "a.calc_c()"
        loop.add_event(print, a)

        # Try the caching where we save the object in the other process then use that object.
        loop.add_event(a.calc_c, cache=True)
        loop.add_event(print, "Cached", a, cache=True)
        loop.add_event(print, "No cache", a)

        b = ABC(5, 7, 0)
        loop.add_event(print, "=====", b, "=====")
        loop.add_event(b.calc_c)
        loop.add_event(print, "No cache", b)
        loop.add_cache_event(b.calc_c)
        loop.add_cache_event(print, "Cached", b)


def test_cache_object():
    a = ABC(1, 2, 0)

    def save_result_object(event_result):
        if isinstance(event_result.event, mp_event_loop.CacheObjectEvent):
            event = event_result.event
            if event.event_key == 'a':
                # Manually set values here
                a.a = event_result.results.a
                a.b = event_result.results.b
                a.c = event_result.results.c
            return True

    with mp_event_loop.get_event_loop(output_handlers=save_result_object) as loop:
        loop.add_event(print, "=====", a, "=====")  # Prints a correctly "ABC(a=1, b=2, c=0)"
        loop.add_event(a.calc_c)  # Does calculation, but doesn't send the result back to us
        # The other process has the correct c value but never passes it back

        # We are passing this a's values down which is 1, 2, 0. We never got the result of "a.calc_c()"
        loop.add_event(print, "No cache", a)

        # Use caching events
        loop.add_event(a.calc_c, cache=True)
        loop.add_event(print, "Cached", a, cache=True)

        # Try getting the object back with save_result_object
        loop.cache_object(a, has_output=True, event_key='a')
        print("Main process", a)
        loop.add_event(print, "No cache", a)  # This fails, because the event has not run and come back yet.
        loop.add_event(print, "Cached", a, cache=True)

    print("Main process after event loop", a)


if __name__ == '__main__':
    # test_object_state()
    test_cache_object()
