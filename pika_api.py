import requests
from playwright.sync_api import sync_playwright
from key import PIKA_EMAIL, PIKA_PASSWORD
from api_base import APIBase
import json
import base64
from time import sleep
from typing import Any, Literal, Union, Optional
import logging
logger = logging.getLogger(__name__)

class PikaAPI(APIBase):
    def __init__(self, email: str = PIKA_EMAIL, password: str = PIKA_PASSWORD, params: Any = ""):
        self.email = email
        self.password = password
        self.token = None
        self.access_token = None
        self.user_id = None

    def login(self) -> str:
        token = ""
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto("https://pika.art/login")
                page.get_by_text("Sign in with an email").click()
                page.wait_for_timeout(1000)
                page.get_by_placeholder("example@gmail.com").fill(self.email)
                page.wait_for_timeout(1000)
                page.get_by_placeholder("Your password").fill(self.password)
                page.wait_for_timeout(1000)
                page.get_by_role("button", name="Sign in").click()
                page.wait_for_timeout(2000)
                cookies = page.context.cookies()
                browser.close()
            except Exception as e:
                print(f"An error occurred: {e}")
                return ""
        if not cookies:
            raise Exception("Login failed, cookie not found.")
        for cookie in cookies:
            if cookie.get("name", "") == "sb-login-auth-token":
                token = cookie.get("value", "")
                break
        self.token = token
        return token
    
    def download_video(self, video_url: str | int, output_path: str) -> None:
        if not video_url or not isinstance(video_url, str):
            raise ValueError("Video URL is empty or invalid.")
        response = requests.get(video_url)
        if response.status_code != 200:
            raise Exception(f"Failed to download video: {response.status_code}")
        with open(output_path, "wb") as f:
            f.write(response.content)

    def parse_token(self, cookie: str) -> tuple[str, str]:
        if not cookie:
            raise ValueError("Cookie is empty or invalid.")
        try:
            decode_jwt_raw = base64.b64decode(cookie.split(".")[0] + "==").decode('utf-8')
            access_token = ""
            user_id = ""
            decode_jwt = json.loads(decode_jwt_raw)
            if "access_token" in decode_jwt:
                access_token = decode_jwt["access_token"]
            if "user" in decode_jwt:
                if "id" in decode_jwt["user"]:
                    user_id = decode_jwt["user"]["id"]
            self.access_token = access_token
            self.user_id = user_id
            return access_token, user_id
        except Exception as e:
            print(f"Failed to decode JWT: {e}")
            return "", ""

    def generate_video(
        self,
        access_token: str,
        images_path: Optional[list[str]] = None,
        image_content: Optional[list[bytes]] = None,
        frame_durations: list[Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]] = None,
        frame_prompts: list[str] = None,
        options: dict[str, Any] = None,
        user_id: str = "",
        loop: Literal["true", "false"] = "false",
    ) -> str:
        if (images_path is None and image_content is None) or (images_path and image_content):
            raise ValueError("Exactly one of images_path or image_content must be provided")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        files: dict[str, Any] = {
            "frameDurations": (None, json.dumps(frame_durations)),
            "transitionPrompts": (None, json.dumps(frame_prompts)),
            "resolution": (None, "1080p"),
            "contentType": (None, "pikaframes"),
            "loop": (None, loop),
            "model": (None, "2.2"),
            "options": (None, json.dumps(options)),
            "userId": (None, user_id),
        }

        if images_path:
            for i, image_path in enumerate(images_path):
                files[f"frame-{i + 1}"] = (image_path, open(image_path, "rb"), "image/png")
            files["contentType"] = (None, "i2v")
            files["image"] = (images_path[0], open(images_path[0], "rb"), "image/png")
        elif image_content:
            for i, content in enumerate(image_content):
                if not content:
                    raise ValueError(f"Image content at index {i} is empty")
                files[f"frame-{i + 1}"] = (f"image_{i + 1}.png", content, "image/png")
            files["contentType"] = (None, "i2v")
            files["image"] = (f"image_1.png", image_content[0], "image/png")

        response = requests.post("https://api.pika.art/generate/v2",
                                headers=headers,
                                files=files)
        data = response.json()
        if not data.get("success"):
            raise Exception(f"Failed to generate video: {data}")
        return data.get("data", {}).get("id", "")
    
    def get_video(self, token: str, video_id: str) -> dict[str, Union[str, int]]:
        cookies = {"sb-login-auth-token": token}
        headers = {"Next-Action": "a4f7d00566d7755f69cb53e2b2bbaf32236f107e"}
        data = json.dumps([{"ids": [video_id]}])
        
        response = requests.post(
            "https://pika.art/library",
            cookies=cookies,
            headers=headers,
            data=data
        )
        logger.debug(f"get_video response for video_id={video_id}: status={response.status_code}, text={response.text}")
        
        if response.status_code != 200:
            logger.error(f"Failed to get video status: HTTP {response.status_code}")
            return {}
        
        try:
            # Парсинг ответа с защитой от неожиданного формата
            lines = response.text.split("\n")
            logger.debug(f"Response lines: {lines}")
            if len(lines) < 2:
                raise ValueError("Response does not contain enough lines")
            json_data = lines[1][2:]  # Убираем префикс
            data = json.loads(json_data)
            video = data["data"]["results"][0]["videos"][0]
            return video
        except (IndexError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing video response: {e}, raw response: {response.text}")
            return {}

    def poll_and_download_video(self, token: str, video_id: str, output_path: str) -> None:
        max_attempts = 30  # Ограничение на количество попыток (5 минут с интервалом 10 сек)
        attempt = 0
        
        while attempt < max_attempts:
            video = self.get_video(token, video_id)
            status = video.get("status", "unknown")
            logger.info(f"Polling video_id={video_id}, attempt={attempt + 1}/{max_attempts}, status={status}")
            
            if not video:
                logger.warning("Empty video response, checking token...")
                token = self.login()  # Обновляем токен, если запрос не удался
                self.parse_token(token[7:])
                continue
            
            if status == "finished":
                self.download_video(video.get("sharingUrl", ""), output_path)
                logger.info(f"Video downloaded to {output_path}")
                return
            elif status in ["failed", "error"]:
                raise Exception(f"Video generation failed with status: {status}")
            
            sleep(10)
            attempt += 1
        
        raise TimeoutError(f"Video status polling timed out after {max_attempts} attempts")

    def send_request(
        self,
        image_paths: Optional[list[str]] = None,
        image_content: Optional[list[bytes]] = None,
        prompt: str = "",
        params: dict[str, Any] = None,
        output_path: str = "output.mp4"
    ) -> str:
        if (image_paths is None and image_content is None) or (image_paths and image_content):
            raise ValueError("Exactly one of image_paths or image_content must be provided")

        if not self.token:
            self.token = self.login()
            logger.info("Logged in and token obtained")
        
        access_token, user_id = self.parse_token(self.token[7:])
        if not access_token or not user_id:
            raise ValueError("Failed to parse token")
        
        gen_video_id = self.generate_video(
            access_token=access_token,
            images_path=image_paths,
            image_content=image_content,
            frame_durations=params.get("frame_durations", [2]),
            frame_prompts=params.get("frame_prompts", [prompt]),
            options=params.get("options", {}),
            user_id=user_id,
            loop=params.get("loop", "false"),
        )
        if not gen_video_id:
            logger.error("Video generation failed: no video ID returned")
            return ""
        
        logger.info(f"Video generation started, video_id={gen_video_id}")
        self.poll_and_download_video(self.token, gen_video_id, output_path)
        return output_path