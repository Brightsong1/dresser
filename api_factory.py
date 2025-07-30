from api_base import APIBase
from gpt_image_api import GptImageAPI
from flux_api import FluxAPI
from kling_api import KlingAPI
from pika_api import PikaAPI
from api_params import GptImageParams, FluxParams, KlingParams

class APIFactory:
    def __init__(self):
        self.api_classes = {
            "gpt_image": GptImageAPI,
            "flux": FluxAPI,
            "kling": KlingAPI,
            "pika": PikaAPI
        }
        self.param_classes = {
            "gpt_image": GptImageParams,
            "flux": FluxParams,
            "kling": KlingParams
        }

    def get_api(self, api_name: str, params: dict = None) -> APIBase:
        api_class = self.api_classes.get(api_name)
        if not api_class:
            raise ValueError(f"API {api_name} не поддерживается")
        
        param_class = self.param_classes.get(api_name)
        if params and param_class:
            api_params = param_class(**params)
        else:
            api_params = param_class() if param_class else None
            
        return api_class(params=api_params)