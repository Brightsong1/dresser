import aiohttp
import asyncio
import logging
from api_base import APIBase
from api_params import KlingParams
from key import GENAPI_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KlingAPI(APIBase):
    def __init__(self, params: KlingParams = None):
        self.params = params or KlingParams()
        self.base_url = "https://api.gen-api.ru/api/v1/networks/kling-elements"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {GENAPI_API_KEY}"
        }

    async def validate_image_urls(self, image_urls):
        async with aiohttp.ClientSession() as session:
            for url in image_urls:
                try:
                    async with session.head(url, headers=self.headers, timeout=5) as response:
                        if response.status != 200:
                            logger.warning(f"Image URL inaccessible: {url} (status: {response.status})")
                            return False
                except Exception as e:
                    logger.warning(f"Failed to validate image URL {url}: {e}")
                    return False
        return True

    async def send_request(self, **kwargs):
        prompt = kwargs.get("prompt")
        image_urls = kwargs.get("image_urls", [])
        params = kwargs.get("params", {})

        if not prompt:
            logger.error("Prompt is required for Kling API")
            raise ValueError("Prompt is required for Kling API")

        if image_urls:
            if not await self.validate_image_urls(image_urls):
                logger.error("One or more image URLs are inaccessible")
                raise ValueError("Invalid or inaccessible image URLs")

        payload = {
            "prompt": prompt,
            "model": params.get("model", self.params.model),
            "duration": params.get("duration", self.params.duration),
            "aspect_ratio": params.get("aspect_ratio", self.params.aspect_ratio),
            "negative_prompt": params.get("negative_prompt", self.params.negative_prompt),
            "translate_input": params.get("translate_input", self.params.translate_input)
        }
        if image_urls:
            payload["input_image_urls"] = image_urls
        if params.get("callback_url"):
            payload["callback_url"] = params.get("callback_url")

        logger.debug(f"Sending payload to Kling API: {payload}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.base_url, json=payload, headers=self.headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Kling API request failed: {response.status} - {error_text}")
                            raise Exception(f"Kling API request failed: {response.status}")
                        data = await response.json()
                        request_id = data.get("request_id")
                        if not request_id:
                            logger.error("No request_id in Kling response")
                            raise Exception("No request_id in Kling response")
                        logger.info(f"Kling task created: {request_id}")

                        video_url = await self._poll_status(request_id)
                        return video_url
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Retrying Kling API request, attempt {attempt + 1}: {e}")
                    await asyncio.sleep(2 ** attempt)
                    continue
                logger.error(f"Kling API request failed after {max_retries} attempts: {e}")
                raise

    async def _poll_status(self, request_id: str) -> str:
        status_url = f"https://api.gen-api.ru/api/v1/request/get/{request_id}"
        max_poll_time = 6000  # 10 minutes
        start_time = asyncio.get_event_loop().time()

        async with aiohttp.ClientSession() as session:
            while True:
                if asyncio.get_event_loop().time() - start_time > max_poll_time:
                    logger.error(f"Polling timeout for Kling task {request_id}")
                    raise Exception(f"Polling timeout for Kling task {request_id}")

                async with session.get(status_url, headers=self.headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to check Kling task status: {response.status} - {error_text}")
                        raise Exception(f"Failed to check Kling task status: {response.status}")
                    data = await response.json()
                    status = data.get("status")
                    logger.info(f"Kling task {request_id} status: {status}")

                    if status == "success":
                        video_url = data.get("output") or (data.get("result")[0] if isinstance(data.get("result"), list) and data.get("result") else None)
                        if not video_url:
                            logger.error(f"No video_url in completed Kling task {request_id}. Full response: {data}")
                            raise Exception(f"No video_url in completed Kling task {request_id}")
                        return video_url
                    elif status == "error":
                        error = data.get("error", "Unknown error")
                        logger.error(f"Kling task {request_id} failed: {error}. Full response: {data}")
                        raise Exception(f"Kling task {request_id} failed: {error}")

                await asyncio.sleep(10)