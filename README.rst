.. image:: https://travis-ci.org/aiolibs/aionursery.svg?branch=master
  :target: https://travis-ci.org/aiolibs/aionursery
  :alt: Build Status
.. image:: https://coveralls.io/repos/github/aiolibs/aionursery/badge.svg?branch=master
  :target: https://coveralls.io/github/aiolibs/aionursery?branch=master
  :alt: Code Coverage

This library implements a task supervisor concept for asyncio_ in the likeness of
`trio's nurseries`_ nurseries. It was inspired by a `blog entry`_ by Nathaniel J. Smith.

It attempts to follow the same design principles as the original:

* It will make sure that all the task spawned from the nursery will have finished one way or the
  other be left running when the ``async with`` block is exited
* If any of the spawned tasks, or the host task running the ``async with`` block, raises an
  exception, all the tasks are cancelled
* If more than one exception is raised by the tasks, a ``aionursery.MultiError`` is raised which
  contains all the raised exceptions in the ``exceptions`` attribute

Here is how to spawn background tasks with a nursery:

.. code-block:: python3

    from asyncio import get_event_loop

    from aionursery import Nursery


    async def main():
        async with Nursery() as nursery:
            nursery.start_soon(your_coroutine_function, arg1, arg2)
            nursery.start_soon(another_coroutine_function, arg1, arg2)

    get_event_loop().run_until_complete(main())

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _blog entry: https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/
.. _trio's nurseries: https://trio.readthedocs.io/en/latest/reference-core.html#tasks-let-you-do-multiple-things-at-once
