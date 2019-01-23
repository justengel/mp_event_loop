import sys
import contextlib
import threading
import multiprocessing as mp
import multiprocessing.queues
from queue import Empty


__all__ = ['PipeProcess']


class PipeProcess(mp.Process):
    """Process to pipe the output of the sub process and redirect it to this sys.stdout and sys.stderr.

    Note:
        The use_queue = True argument will pass data between processes using Queues instead of Pipes. Queues will
        give you the full output and read all of the data from the Queue. A pipe is more efficient, but may not
        redirect all of the output back to the main process.
    """
    def __init__(self, group=None, target=None, name=None, args=tuple(), kwargs={}, *_, daemon=None,
                 use_pipe=None, use_queue=None):
        self.read_out_th = None
        self.read_err_th = None
        self.pipe_target = target
        self.pipe_alive = mp.Event()

        if use_pipe or (use_pipe is None and not use_queue):  # Default
            self.parent_stdout, self.child_stdout = mp.Pipe(False)
            self.parent_stderr, self.child_stderr = mp.Pipe(False)
        else:
            self.parent_stdout = self.child_stdout = mp.Queue()
            self.parent_stderr = self.child_stderr = mp.Queue()

        args = (self.child_stdout, self.child_stderr, target) + tuple(args)
        target = self.run_pipe_out_target

        super(PipeProcess, self).__init__(group=group, target=target, name=name, args=args, kwargs=kwargs,
                                          daemon=daemon)

    def start(self):
        """Start the multiprocess and reading thread."""
        self.pipe_alive.set()
        super(PipeProcess, self).start()

        self.read_out_th = threading.Thread(target=self.read_pipe_out,
                                            args=(self.pipe_alive, self.parent_stdout, sys.stdout))
        self.read_err_th = threading.Thread(target=self.read_pipe_out,
                                            args=(self.pipe_alive, self.parent_stderr, sys.stderr))
        self.read_out_th.daemon = True
        self.read_err_th.daemon = True
        self.read_out_th.start()
        self.read_err_th.start()

    @classmethod
    def run_pipe_out_target(cls, pipe_stdout, pipe_stderr, pipe_target, *args, **kwargs):
        """The real multiprocessing target to redirect stdout and stderr to a pipe or queue."""
        sys.stdout.write = cls.redirect_write(pipe_stdout)  # , sys.__stdout__)  # Is redirected in main process
        sys.stderr.write = cls.redirect_write(pipe_stderr)  # , sys.__stderr__)  # Is redirected in main process

        pipe_target(*args, **kwargs)

    @staticmethod
    def redirect_write(child, out=None):
        """Create a function to write out a pipe and write out an additional out."""
        if isinstance(child, mp.queues.Queue):
            send = child.put
        else:
            send = child.send_bytes  # No need to pickle with child_conn.send(data)

        def write(data, *args):
            try:
                if isinstance(data, str):
                    data = data.encode('utf-8')

                send(data)
                if out is not None:
                    out.write(data)
            except:
                pass
        return write

    @classmethod
    def read_pipe_out(cls, pipe_alive, pipe_out, out):
        if isinstance(pipe_out, mp.queues.Queue):
            # Queue has better functionality to get all of the data
            def recv():
                return pipe_out.get(timeout=0.5)

            def is_alive():
                return pipe_alive.is_set() or pipe_out.qsize() > 0
        else:
            # Pipe is more efficient
            recv = pipe_out.recv_bytes  # No need to unpickle with data = pipe_out.recv()
            is_alive = pipe_alive.is_set

        # Loop through reading and redirecting data
        while is_alive():
            try:
                data = recv()
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                out.write(data)
            except EOFError:
                break
            except Empty:
                pass
            except:
                pass

    def join(self, *args):
        # Wait for process to finish (unless a timeout was given)
        super(PipeProcess, self).join(*args)

        # Trigger to stop the threads
        self.pipe_alive.clear()

        # Pipe must close to prevent blocking and waiting on recv forever
        if not isinstance(self.parent_stdout, mp.queues.Queue):
            with contextlib.suppress():
                self.parent_stdout.close()
            with contextlib.suppress():
                self.parent_stderr.close()

        # Close the pipes and threads
        with contextlib.suppress():
            self.read_out_th.join()
        with contextlib.suppress():
            self.read_err_th.join()
