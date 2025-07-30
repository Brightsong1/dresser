import typing
from typing import Literal, Any

class GptImageParams:
    def __init__(self, callback_url: str = None, is_sync: bool = False, prompt: str = "",
                 image: list = None, mask: str = None, background: str = "auto",
                 model: str = "gpt-image-1", moderation: str = "auto", n: int = 1,
                 output_format: str = "png", quality: str = "high", size: str = "1024x1536"):
        self.callback_url = callback_url
        self.is_sync = is_sync
        self.prompt = prompt
        self.image = image or []
        self.mask = mask
        self.background = background
        self.model = model
        self.moderation = moderation
        self.n = n
        self.output_format = output_format
        self.quality = quality
        self.size = size

class FluxParams:
    def __init__(self, callback_url: str = None, translate_input: bool = True, seed: int = None,
                 model: str = "ultra", width: int = 1024, height: int = 1536,
                 num_inference_steps: int = 36, guidance_scale: float = 7.5,
                 num_images: int = 1, enable_safety_checker: bool = False, strength: float = 0.45,
                 is_sync: bool = False):
        self.callback_url = callback_url
        self.translate_input = translate_input
        self.seed = seed
        self.model = model
        self.width = width
        self.height = height
        self.num_inference_steps = num_inference_steps
        self.guidance_scale = guidance_scale
        self.num_images = num_images
        self.enable_safety_checker = enable_safety_checker
        self.strength = strength
        self.is_sync = is_sync

class KlingParams:
    def __init__(self, callback_url: str = None, translate_input: bool = True,
                 model: str = "pro", duration: int = 5, aspect_ratio: str = "9:16",
                 negative_prompt: str = "blur, distort, and low quality",
                 prompt: str = "Девочка играет с кроликом в сказочном саду"):
        self.callback_url = callback_url
        self.translate_input = translate_input
        self.model = model
        self.duration = duration
        self.aspect_ratio = aspect_ratio
        self.negative_prompt = negative_prompt
        self.prompt = prompt