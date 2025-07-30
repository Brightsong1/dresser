import aiohttp
import asyncio
import logging
from api_base import APIBase
from api_params import FluxParams
from key import GENAPI_API_KEY
from retry_util import retry_request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FluxAPI(APIBase):
    def __init__(self, params: FluxParams = None):
        self.params = params or FluxParams()
        self.base_url = "https://api.gen-api.ru/api/v1/networks/flux"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {GENAPI_API_KEY}"
        }

    @retry_request(max_retries=0, timeout=500, backoff_factor=2)
    async def send_request(self, **kwargs):
        prompt = kwargs.get("prompt")
        image_url = kwargs.get("image_url")
        params = kwargs.get("params", {})

        if not prompt:
            logger.error(f"Prompt is required: prompt={prompt}")
            raise ValueError("Prompt is required")

        payload = {
            "prompt": prompt,
            "model": params.get("model", self.params.model),
            "width": params.get("width", self.params.width),
            "height": params.get("height", self.params.height),
            "num_inference_steps": params.get("num_inference_steps", self.params.num_inference_steps),
            "guidance_scale": params.get("guidance_scale", self.params.guidance_scale),
            "strength": params.get("strength", self.params.strength),
            "translate_input": params.get("translate_input", self.params.translate_input),
            "is_sync": params.get("is_sync", self.params.is_sync)
        }
        if image_url:
            payload["image"] = image_url
        if params.get("callback_url", self.params.callback_url):
            payload["callback_url"] = params.get("callback_url", self.params.callback_url)
        if params.get("seed", self.params.seed) is not None:
            payload["seed"] = params.get("seed", self.params.seed)

        logger.debug(f"Sending payload to Flux API: {payload}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload, headers=self.headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Flux API request failed: {response.status} - {error_text}")
                        raise Exception(f"Flux API request failed: {response.status}")
                    data = await response.json()
                    if params.get("is_sync", self.params.is_sync):
                        image_url = None
                        result = data.get("result")
                        if isinstance(result, list) and result:
                            image_url = result[0]
                        else:
                            image_url = data.get("output")
                        if not image_url:
                            logger.error(f"No image_url in synchronous Flux response: {data}")
                            raise Exception("No image_url in synchronous Flux response")
                        return image_url
                    task_id = data.get("request_id")
                    if not task_id:
                        logger.error("No request_id in Flux response")
                        raise Exception("No request_id in Flux response")
                    logger.info(f"Flux task created: {task_id}")

            image_url = await self._poll_status(task_id)
            return image_url

        except Exception as e:
            logger.error(f"Flux API error: {e}")
            raise Exception(f"Flux API error: {e}")

    @retry_request(max_retries=0, timeout=300, backoff_factor=2)
    async def _poll_status(self, task_id: str) -> str:
        status_url = f"https://api.gen-api.ru/api/v1/request/get/{task_id}"
        max_poll_time = 600
        start_time = asyncio.get_event_loop().time()

        async with aiohttp.ClientSession() as session:
            while True:
                if asyncio.get_event_loop().time() - start_time > max_poll_time:
                    logger.error(f"Polling timeout for Flux task {task_id}")
                    raise Exception(f"Polling timeout for Flux task {task_id}")

                async with session.get(status_url, headers=self.headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to check Flux task status: {response.status} - {error_text}")
                        raise Exception(f"Failed to check Flux task status: {response.status}")
                    data = await response.json()
                    status = data.get("status")
                    logger.info(f"Flux task {task_id} status: {status}")

                    if status == "success":
                        image_url = None
                        result = data.get("result")
                        if isinstance(result, list) and result:
                            image_url = result[0]
                        else:
                            image_url = data.get("output")
                        if not image_url:
                            logger.error(f"No image_url in completed Flux task {task_id}. Full response: {data}")
                            raise Exception(f"No image_url in completed Flux task {task_id}")
                        return image_url
                    elif status == "error":
                        error = data.get("error", "Unknown error")
                        logger.error(f"Flux task {task_id} failed: {error}. Full response: {data}")
                        raise Exception(f"Flux task {task_id} failed: {error}")

                await asyncio.sleep(10)