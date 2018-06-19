import asyncio
from asyncio import Queue, CancelledError

import pytest

from aionursery import Nursery, MultiError, NurseryError


class TestMultiError:
    @pytest.fixture
    def error(self):
        return MultiError([ValueError('blah'), KeyError('foo')])

    def test_str(self, error):
        assert str(error) == "ValueError('blah',), KeyError('foo',)"

    def test_repr(self, error):
        assert repr(error) == "<MultiError: ValueError('blah',), KeyError('foo',)>"


class TestNursery:
    @staticmethod
    async def delayed_put(queue: Queue, item, delay: float = 0.1):
        await asyncio.sleep(delay)
        await queue.put(item)

    @staticmethod
    async def async_error(text, delay=0.1):
        try:
            if delay:
                await asyncio.sleep(delay)
        finally:
            raise Exception(text)

    @pytest.fixture
    def queue(self) -> Queue:
        return Queue()

    def test_nursery_not_opened(self):
        exc = pytest.raises(NurseryError, Nursery().start_soon, self.async_error, 'fail')
        exc.match('This nursery has not been opened yet')

    @pytest.mark.asyncio
    async def test_nursery_already_running(self):
        with pytest.raises(NurseryError) as exc:
            async with Nursery() as nursery, nursery:
                pass

        exc.match('This nursery is already running')

    @pytest.mark.asyncio
    async def test_nursery_already_stopped(self):
        async with Nursery() as nursery:
            pass

        exc = pytest.raises(NurseryError, nursery.start_soon, self.async_error, 'fail')
        exc.match('This nursery has already been closed')

    @pytest.mark.asyncio
    async def test_success(self, queue):
        async with Nursery() as nursery:
            nursery.start_soon(queue.put, 'a')
            nursery.start_soon(queue.put, 'b')

        assert queue.get_nowait() == 'a'
        assert queue.get_nowait() == 'b'

    @pytest.mark.asyncio
    async def test_host_exception(self, queue):
        with pytest.raises(Exception) as exc:
            async with Nursery() as nursery:
                nursery.start_soon(self.delayed_put, queue, 'a', 5)
                raise Exception('dummy error')

        exc.match('dummy error')
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_host_cancelled_before_aexit(self, queue):
        with pytest.raises(asyncio.CancelledError):
            async with Nursery() as nursery:
                nursery.start_soon(self.delayed_put, queue, 'a')
                raise CancelledError

        assert queue.empty()

    @pytest.mark.asyncio
    async def test_host_cancelled_during_aexit(self, event_loop, queue):
        with pytest.raises(asyncio.CancelledError):
            async with Nursery() as nursery:
                nursery.start_soon(self.delayed_put, queue, 'a')
                event_loop.call_soon(asyncio.Task.current_task().cancel)

        assert queue.empty()

    @pytest.mark.asyncio
    async def test_multi_error(self):
        with pytest.raises(MultiError) as exc:
            async with Nursery() as nursery:
                nursery.start_soon(self.async_error, 'task1')
                nursery.start_soon(self.async_error, 'task2')

        assert len(exc.value.exceptions) == 2
        assert sorted(str(e) for e in exc.value.exceptions) == ['task1', 'task2']

    @pytest.mark.asyncio
    async def test_multi_error_host(self):
        with pytest.raises(MultiError) as exc:
            async with Nursery() as nursery:
                nursery.start_soon(self.async_error, 'child', delay=2)
                await asyncio.sleep(0.1)
                raise Exception('host')

        assert len(exc.value.exceptions) == 2
        assert [str(e) for e in exc.value.exceptions] == ['host', 'child']
