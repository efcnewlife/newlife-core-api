"""
Task concurrency
"""
import asyncio
from typing import List, Union, Coroutine

CONCURRENT_NUMBER = 10
semaphore = asyncio.Semaphore(CONCURRENT_NUMBER)


async def concurrency_worker(futures: List[Union[asyncio.Future, Coroutine]], return_exceptions: bool = False):
    """
    concurrency worker
    :param futures:
    :param return_exceptions:
    :return:
    """
    async with semaphore:
        return await asyncio.gather(*futures, return_exceptions=return_exceptions)
