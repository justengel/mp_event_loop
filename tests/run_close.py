"""
Check if the loop closes successfully without any directive to stop.
"""
import mp_event_loop


def add_vals(value, value2=1):
    print(value + value2)
    return value + value2


def run_loop_atexit():
    """If this function runs twice it will fail."""
    results = []

    def save_results(event):
        results.append(event.results)

    loop = mp_event_loop.get_event_loop(output_handlers=save_results)
    loop.start()

    loop.add_event(add_vals, 1, 2)
    loop.add_event(add_vals, 2, 3)
    loop.add_event(add_vals, 3, 4)
    loop.add_event(add_vals, 4, 5)

    print("Results:", results)
    print('Just make sure the python process closes')


def run_joinable_queue_task_done():
    """Test if I need to mark task done on a joinable queue that has a timeout."""
    import time
    from queue import Empty
    from multiprocessing import JoinableQueue
    que = JoinableQueue()

    que.put(1)
    one = que.get(timeout=1)
    que.task_done()

    try:
        two_fail = que.get(timeout=1)
    except Empty:
        pass

    que.put(2)
    two = que.get(timeout=1)
    que.task_done()

    que.put(3)
    three = que.get(timeout=1)
    que.task_done()

    que.join()
    print('end')


if __name__ == '__main__':
    run_loop_atexit()
    # run_joinable_queue_task_done()
