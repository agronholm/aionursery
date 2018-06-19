from asyncio import Task, wait, CancelledError, get_event_loop
from enum import Enum
from typing import Callable, TypeVar, Awaitable, Set, cast, Tuple, Sequence

T_Retval = TypeVar('T_Retval')


class MultiError(Exception):
    """Raised when multiple exceptions have been raised in tasks running in parallel."""

    def __init__(self, exceptions: Sequence[BaseException]) -> None:
        super().__init__(exceptions)

        self.msg = ''
        for i, exc in enumerate(exceptions, 1):
            if i > 1:
                self.msg += '\n\n'

            self.msg += 'Details of embedded exception {}:\n\n  {}: {}'.format(
                i, exc.__class__.__name__, exc)

    @property
    def exceptions(self) -> Sequence[BaseException]:
        return self.args[0]

    def __str__(self):
        return ', '.join('{}{}'.format(exc.__class__.__name__, exc.args) for exc in self.args[0])

    def __repr__(self) -> str:
        return '<{}: {}>'.format(self.__class__.__name__,
                                 ', '.join(repr(exc) for exc in self.args[0]))


class NurseryError(Exception):
    """Raised when there's a problem with the nursery."""


class NurseryStatus(Enum):
    initial = 1
    running = 2
    closed = 3


class Nursery:
    __slots__ = '_loop', '_status', '_host_task', '_tasks'

    def __init__(self) -> None:
        self._status = NurseryStatus.initial
        self._tasks = set()  # type: Set[Task]

    def _assert_status(self, expected: NurseryStatus) -> None:
        if self._status is expected:
            return
        elif self._status is NurseryStatus.initial:
            raise NurseryError('This nursery has not been opened yet')
        elif self._status is NurseryStatus.running:
            raise NurseryError('This nursery is already running')
        else:
            raise NurseryError('This nursery has already been closed')

    def _task_finished(self, task: Task) -> None:
        # If a task raised an exception (other than CancelledError), cancel all other tasks
        if not task.cancelled() and task.exception() is not None:
            if self._status is NurseryStatus.running:
                self._status = NurseryStatus.closed
                self._host_task.cancel()
                for task in self._tasks:
                    task.cancel()
        else:
            self._tasks.discard(task)

    def start_soon(self, func: Callable[..., Awaitable], *args, **kwargs) -> None:
        self._assert_status(NurseryStatus.running)
        task = self._loop.create_task(func(*args, **kwargs))
        self._tasks.add(task)
        task.add_done_callback(self._task_finished)

    async def __aenter__(self) -> 'Nursery':
        self._assert_status(NurseryStatus.initial)
        self._status = NurseryStatus.running
        self._loop = get_event_loop()
        self._host_task = Task.current_task(self._loop)  # type: Task
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        exceptions = []
        if exc_val is not None:
            # The host task raised an exception or was cancelled externally
            for task in self._tasks:
                task.cancel()

            if exc_type is not CancelledError:
                exceptions.append(exc_val)

        cancel_exception = None
        while self._tasks:
            try:
                done, _pending = cast(Tuple[Set[Task], Set[Task]], await wait(self._tasks))
                for task in done:
                    self._tasks.discard(task)
                    if not task.cancelled() and task.exception():
                        exceptions.append(task.exception())
            except CancelledError as e:
                cancel_exception = e
                for future in self._tasks:
                    future.cancel()

        self._status = NurseryStatus.closed
        if len(exceptions) > 1:
            raise MultiError(exceptions)
        elif len(exceptions) == 1:
            raise exceptions[0]
        elif cancel_exception:
            raise cancel_exception
