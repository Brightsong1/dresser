import aiohttp
import asyncio
import logging
from api_base import APIBase
from api_params import GptImageParams
from key import GENAPI_API_KEY as GPT_IMAGE_API_KEY
from retry_util import retry_request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GptImageAPI(APIBase):
    def __init__(self, params: GptImageParams = None):
        self.params = params or GptImageParams()
        self.base_url = "https://api.gen-api.ru/api/v1/networks/gpt-image-1"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {GPT_IMAGE_API_KEY}"
        }

    @retry_request(max_retries=0, timeout=500, backoff_factor=2)
    async def send_request(self, **kwargs):
        prompt = kwargs.get("prompt")
        image_urls = kwargs.get("image_urls", [])
        params = kwargs.get("params", {})
        is_sync = params.get("is_sync", self.params.is_sync)

        if not prompt:
            logger.error("Prompt is required for gpt-image-1")
            raise ValueError("Prompt is required for gpt-image-1")

        moderation = params.get("moderation", self.params.moderation)
        valid_moderation = ["auto", "low", "high"]
        if moderation not in valid_moderation:
            logger.warning(f"Invalid moderation value: {moderation}. Using default: {self.params.moderation}")
            moderation = self.params.moderation

        payload = {
            "prompt": prompt,
            "is_sync": is_sync,
            "model": params.get("model", self.params.model),
            "moderation": moderation,
            "n": params.get("n", self.params.n),
            "output_format": params.get("output_format", self.params.output_format),
            "quality": params.get("quality", self.params.quality),
            "size": params.get("size", self.params.size),
            "image": image_urls or self.params.image
        }

        logger.debug(f"Sending payload to gpt-image-1 API: {payload}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload, headers=self.headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"gpt-image-1 API request failed: {response.status} - {error_text}")
                        raise Exception(f"gpt-image-1 API request failed: {response.status}")
                    data = await response.json()
                    if is_sync:
                        image_url = data.get("result", [None])[0] or data.get("output")
                        if not image_url:
                            logger.error(f"No image_url in synchronous gpt-image-1 response: {data}")
                            raise Exception("No image_url in synchronous gpt-image-1 response")
                        return image_url
                    request_id = data.get("request_id")
                    if not request_id:
                        logger.error("No request_id in gpt-image-1 response")
                        raise Exception("No request_id in gpt-image-1 response")
                    logger.info(f"gpt-image-1 task created: {request_id}")

            image_url = await self._poll_status(request_id)
            return image_url

        except Exception as e:
            logger.error(f"gpt-image-1 API error: {e}")
            raise Exception(f"gpt-image-1 API error: {e}")

    @retry_request(max_retries=0, timeout=500, backoff_factor=2)
    async def _poll_status(self, request_id: str) -> str:
        status_url = f"https://api.gen-api.ru/api/v1/request/get/{request_id}"
        max_poll_time = 600
        start_time = asyncio.get_event_loop().time()

        async with aiohttp.ClientSession() as session:
            while True:
                if asyncio.get_event_loop().time() - start_time > max_poll_time:
                    logger.error(f"Polling timeout for gpt-image-1 task {request_id}")
                    raise Exception(f"Polling timeout for gpt-image-1 task {request_id}")

                async with session.get(status_url, headers=self.headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to check gpt-image-1 task status: {response.status} - {error_text}")
                        raise Exception(f"Failed to check gpt-image-1 task status: {response.status}")
                    data = await response.json()
                    status = data.get("status")
                    logger.info(f"gpt-image-1 task {request_id} status: {status}")

                    if status == "success":
                        image_url = None
                        result = data.get("result")
                        if isinstance(result, list) and result:
                            image_url = result[0]
                        else:
                            image_url = data.get("output")
                        if not image_url:
                            logger.error(f"No image_url in completed gpt-image-1 task {request_id}. Full response: {data}")
                            raise Exception(f"Failed to retrieve image URL for gpt-image-1 task {request_id}. Response missing valid image URL.")
                        return image_url
                    elif status == "error":
                        error = data.get("error", "Unknown error")
                        logger.error(f"gpt-image-1 task {request_id} failed: {error}. Full response: {data}")
                        raise Exception(f"gpt-image-1 task {request_id} failed: {error}")

                await asyncio.sleep(10)