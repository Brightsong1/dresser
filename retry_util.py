import asyncio
import functools
import logging
from aiohttp import ClientSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def retry_request(max_retries=0, timeout=300, backoff_factor=2):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                async with asyncio.timeout(timeout):
                    return await func(*args, **kwargs)
            except asyncio.TimeoutError:
                logger.warning(f"Request timed out after {timeout}s")
                raise Exception("Request timed out")
            except Exception as e:
                logger.error(f"Error during request: {e}")
                raise Exception(f"Request failed: {e}")
        return wrapper
    return decorator