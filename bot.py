import logging
import asyncio
import aiohttp
import re
import inspect
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from telegram.error import TimedOut
from telegram_wrapper import TelegramHandler
from api_factory import APIFactory
from key import TOKEN, OPENAI_API_KEY
from openai import AsyncOpenAI
import base64
import os

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

class Bot:
    def __init__(self):
        self.telegram_handler = TelegramHandler()
        self.api_factory = APIFactory()
        self.openai_client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url="https://api.openai.com/v1"
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.debug("Получена команда /start")
        await update.message.reply_text(
            "Привет! Отправь одно или несколько фото с подписью."
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.debug(f"Получено сообщение: photo={bool(update.message.photo)}, text={update.message.caption}")
        user_id = update.effective_user.id
        photos = update.message.photo
        user_query = update.message.caption or "Create a video based on these photos"

        try:
            photo_groups = {photos[-1]} 
            unique_photos = [photos[-1]]
            logger.info(f"Найдено уникальных фотографий: {len(unique_photos)}")

            photo_urls = []
            photo_base64_list = []
            async with aiohttp.ClientSession() as session:
                for i, photo in enumerate(unique_photos):
                    logger.debug(f"Получение URL фото {i} для user_id={user_id}, file_unique_id={photo.file_unique_id}")
                    file = await photo.get_file()
                    file_path = re.sub(r'^https?://api\.telegram\.org/file/bot[^/]+/', '', file.file_path)
                    file_path = file_path.lstrip('/')
                    photo_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
                    photo_urls.append(photo_url)
                    logger.info(f"Фото {i} URL: {photo_url} (file_unique_id={photo.file_unique_id})")
                    
                    async with session.get(photo_url) as response:
                        if response.status != 200:
                            logger.error(f"Не удалось скачать фото {i}: {response.status}")
                            await update.message.reply_text(
                                f"Не удалось скачать фото {i} (ошибка {response.status}). Попробуйте другие фото."
                            )
                            return
                        photo_data = await response.read()
                        photo_base64 = base64.b64encode(photo_data).decode('utf-8')
                        photo_base64_list.append(f"data:image/jpeg;base64,{photo_base64}")
                        logger.info(f"Фото {i} успешно закодировано в base64")

            async with aiohttp.ClientSession() as session:
                for i, photo_url in enumerate(photo_urls):
                    async with session.head(photo_url) as response:
                        if response.status != 200:
                            logger.error(f"Photo {i} URL inaccessible: {response.status}")
                            await update.message.reply_text(
                                f"Не удалось получить доступ к фото {i} (ошибка {response.status}). Попробуйте другие фото."
                            )
                            return

            await update.message.reply_text(f"Обрабатываю фото...")

            try:
                response = await self.openai_client.chat.completions.create(
                    model="o3",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Based on the user's request: '{user_query}', generate prompts for a 20-second video, divided into 1 to 4 distinct scenes (each 5 seconds if 4 scenes, adjust duration proportionally for fewer scenes). The number of scenes should be chosen to best fit a cohesive narrative based on the request and images. For each scene, create two prompts: one for a highly realistic still image and one for a dynamic video clip. Additionally, create a highly detailed prompt for a final still image (final frame). Image prompts should describe detailed, photorealistic scenes with consistent textures (e.g., wood grain, fabric details), lighting (e.g., soft natural light or dramatic shadows), colors (e.g., specific color palettes), and background across all scenes and the final frame unless explicitly requested otherwise. Video prompts should describe dynamic scenes with smooth motion, deliberate camera movement (e.g., pan, zoom, tracking), and immersive atmosphere, ensuring narrative continuity and consistent visual style. The final frame should be a photorealistic still image that logically concludes the narrative, emphasizing key elements from previous scenes (e.g., a significant object, character, or setting detail) with enhanced realism through detailed textures, lifelike lighting, and subtle imperfections (e.g., slight wear on objects, natural shadows). Ensure smooth transitions between scenes and a logical, visually compelling conclusion with the final frame to form a unified video without abrupt changes in style or setting. Format the response as:\n\nNumber of scenes: [number]\nScene 1 Image prompt: [prompt]\nScene 1 Video prompt: [prompt]\n[Repeat for each scene up to the chosen number]\nFinal Frame Image prompt: [prompt]\n\nExample:\nNumber of scenes: 3\nScene 1 Image prompt: A young woman in a flowing white dress with intricate lace patterns stands in a sunlit lavender field at golden hour, holding a vintage leather book with worn edges. Her hair gently blows in the breeze, and a rustic wooden fence in the background is partially covered with ivy, with soft sunlight casting delicate shadows on the ground.\nScene 1 Video prompt: A young woman in a white lace dress walks through a lavender field at sunset, the camera tracking her as she runs her hands over the flowers, with a vintage book tucked under her arm. The scene shifts to reveal a rustic fence with ivy, as golden light filters through the plants and a gentle breeze moves her hair.\nScene 2 Image prompt: The same woman sits on a weathered wooden bench in the lavender field, reading the vintage book, with soft sunlight filtering through her hair and casting intricate shadows from the ivy-covered fence in the background.\nScene 2 Video prompt: The camera pans around the woman sitting on a bench in the lavender field, reading her book, as a gentle breeze rustles the pages and lavender plants sway in the background, with golden light enhancing the scene’s warmth.\nScene 3 Image prompt: The woman closes the book and looks toward the horizon, with the lavender field stretching into the distance under a golden sky, the fence faintly visible in the background.\nScene 3 Video prompt: The camera follows the woman’s gaze as she closes her book and looks toward the horizon, zooming out to show the expansive lavender field under a golden sunset, with subtle movements of lavender in the breeze.\nFinal Frame Image prompt: ..."
                                },
                                *[
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": photo_base64
                                        }
                                    }
                                    for photo_base64 in photo_base64_list
                                ]
                            ]
                        }
                    ]
                )
                scenario = response.choices[0].message.content.strip()
                logger.debug(f"OpenAI o1 response: {scenario}")
                
                prompts = {}
                lines = [line.strip() for line in scenario.split('\n') if line.strip()]
                num_scenes = 4  
                for line in lines:
                    if line.startswith("Number of scenes:"):
                        num_scenes = min(int(line.split(":")[1].strip()), 4)
                        logger.info(f"Model selected {num_scenes} scenes")
                    for scene in range(1, 5):
                        if line.startswith(f"Scene {scene} Image prompt:"):
                            prompts[f"scene_{scene}_image"] = line[len(f"Scene {scene} Image prompt:"):].strip()
                        elif line.startswith(f"Scene {scene} Video prompt:"):
                            prompts[f"scene_{scene}_video"] = line[len(f"Scene {scene} Video prompt:"):].strip()
                    if line.startswith("Final Frame Image prompt:"):
                        prompts["final_frame_image"] = line[len("Final Frame Image prompt:"):].strip()
                
                for scene in range(1, num_scenes + 1):
                    if f"scene_{scene}_image" not in prompts or f"scene_{scene}_video" not in prompts:
                        logger.warning(f"Missing prompt for scene {scene}. Using fallback.")
                        prompts[f"scene_{scene}_image"] = f"A detailed realistic scene {scene} inspired by: {user_query}, maintaining consistent background and style"
                        prompts[f"scene_{scene}_video"] = f"A dynamic video scene {scene} inspired by: {user_query}, maintaining consistent background and style"
                if "final_frame_image" not in prompts:
                    logger.warning("Missing final frame prompt. Using fallback.")
                    prompts["final_frame_image"] = f"A concluding realistic image inspired by: {user_query}, maintaining consistent background and style"
                logger.info(f"Generated prompts: {prompts}")
            except Exception as e:
                logger.error(f"Ошибка генерации промптов: {e}")
                await update.message.reply_text(f"Ошибка генерации промптов: {e}. Использую запасные промпты.")
                num_scenes = 4  
                prompts = {}
                for scene in range(1, num_scenes + 1):
                    prompts[f"scene_{scene}_image"] = f"A detailed realistic scene {scene} inspired by: {user_query}, maintaining consistent background and style"
                    prompts[f"scene_{scene}_video"] = f"A dynamic video scene {scene} inspired by: {user_query}, maintaining consistent background and style"
                prompts["final_frame_image"] = f"A concluding realistic image inspired by: {user_query}, maintaining consistent background and style"
                logger.info(f"Fallback prompts generated: {prompts}")

            os.makedirs("temp", exist_ok=True)

            previous_enhanced_url = None
            for scene in range(1, num_scenes + 1):
                image_prompt = prompts[f"scene_{scene}_image"]
                await update.message.reply_text(f"Обрабатываю сцену {scene}...")

                generated_image_url = None
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        logger.debug(f"Вызов gpt-image-1 API для сцены {scene}, попытка {attempt + 1}/{max_retries}")
                        gpt_image_api = self.api_factory.get_api("gpt_image")
                        image_urls = photo_urls + ([previous_enhanced_url] if previous_enhanced_url else [])
                        generated_image_url = await gpt_image_api.send_request(
                            prompt=f"{image_prompt}, maintain consistent background, lighting, and style across all scenes unless explicitly requested otherwise",
                            image_urls=image_urls,
                            params={
                                "size": "1024x1536",
                                "quality": "high",
                                "output_format": "png",
                                "is_sync": False,
                                "moderation": "auto",
                                "n": 1
                            }
                        )
                        logger.info(f"Сцена {scene} изображение сгенерировано: {generated_image_url}")
                        async with aiohttp.ClientSession() as session:
                            async with session.get(generated_image_url) as response:
                                if response.status != 200:
                                    raise Exception(f"Failed to download generated image for scene {scene}: {response.status}")
                                temp_image_path = f"temp/generated_{user_id}_scene_{scene}.png"
                                with open(temp_image_path, "wb") as f:
                                    content = await response.read()
                                    if not content:
                                        raise ValueError(f"Empty content downloaded for scene {scene}")
                                    f.write(content)
                                if not os.path.exists(temp_image_path) or os.path.getsize(temp_image_path) == 0:
                                    raise FileNotFoundError(f"Generated image file for scene {scene} is missing or empty: {temp_image_path}")
                        await update.message.reply_photo(
                            open(temp_image_path, "rb"),
                            caption=f"Сгенерированное изображение для сцены {scene}"
                        )
                        break
                    except Exception as e:
                        logger.error(f"Ошибка генерации изображения для сцены {scene}, попытка {attempt + 1}: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        logger.error(f"Не удалось сгенерировать изображение для сцены {scene} после {max_retries} попыток")
                        await update.message.reply_text(
                            f"Не удалось сгенерировать изображение для сцены {scene}: {e}. Продолжаю с следующей сценой."
                        )
                        break

                if not generated_image_url:
                    continue

                try:
                    logger.debug(f"Вызов Flux API для сцены {scene}")
                    flux_api = self.api_factory.get_api("flux")
                    enhanced_image_url = await flux_api.send_request(
                        prompt=f"Enhance the realism of this image, preserving all background elements, non-clothing details, and textures exactly as they are, maintaining consistent style, lighting, and colors across all scenes",
                        image_url=generated_image_url,
                        params={
                            "width": 1024,
                            "height": 1536,
                            "model": "ultra",
                            "num_inference_steps": 36,
                            "guidance_scale": 7.5,
                            "strength": 0.3,
                            "is_sync": False,
                            "preserve_background": True
                        }
                    )
                    logger.info(f"Сцена {scene} изображение улучшено: {enhanced_image_url}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(enhanced_image_url) as response:
                            if response.status != 200:
                                raise Exception(f"Failed to download enhanced image for scene {scene}: {response.status}")
                            temp_enhanced_path = f"temp/enhanced_{user_id}_scene_{scene}.png"
                            with open(temp_enhanced_path, "wb") as f:
                                content = await response.read()
                                if not content:
                                    raise ValueError(f"Empty content downloaded for enhanced scene {scene}")
                                f.write(content)
                            # Verify file exists and is not empty
                            if not os.path.exists(temp_enhanced_path) or os.path.getsize(temp_enhanced_path) == 0:
                                raise FileNotFoundError(f"Enhanced image file for scene {scene} is missing or empty: {temp_enhanced_path}")
                    await update.message.reply_photo(
                        open(temp_enhanced_path, "rb"),
                        caption=f"Улучшенное изображение для сцены {scene}"
                    )
                    previous_enhanced_url = enhanced_image_url
                except Exception as e:
                    logger.error(f"Ошибка улучшения изображения для сцены {scene}: {e}")
                    await update.message.reply_text(
                        f"Ошибка улучшения изображения для сцены {scene}: {e}. Продолжаю с следующей сценой."
                    )
                    continue

            await update.message.reply_text("Обрабатываю завершающий кадр...")
            final_image_prompt = prompts["final_frame_image"]
            generated_image_url = None
            for attempt in range(max_retries):
                try:
                    logger.debug(f"Вызов gpt-image-1 API для завершающего кадра, попытка {attempt + 1}/{max_retries}")
                    gpt_image_api = self.api_factory.get_api("gpt_image")
                    image_urls = photo_urls + ([previous_enhanced_url] if previous_enhanced_url else [])
                    generated_image_url = await gpt_image_api.send_request(
                        prompt=f"{final_image_prompt}, maintain consistent background, lighting, and style with previous scenes",
                        image_urls=image_urls,
                        params={
                            "size": "1024x1536",
                            "quality": "high",
                            "output_format": "png",
                            "is_sync": False,
                            "moderation": "auto",
                            "n": 1
                        }
                    )
                    logger.info(f"Завершающий кадр сгенерирован: {generated_image_url}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(generated_image_url) as response:
                            if response.status != 200:
                                raise Exception(f"Failed to download generated final frame: {response.status}")
                            temp_image_path = f"temp/generated_{user_id}_final_frame.png"
                            with open(temp_image_path, "wb") as f:
                                content = await response.read()
                                if not content:
                                    raise ValueError(f"Empty content downloaded for final frame")
                                f.write(content)
                            # Verify file exists and is not empty
                            if not os.path.exists(temp_image_path) or os.path.getsize(temp_image_path) == 0:
                                raise FileNotFoundError(f"Generated final frame file is missing or empty: {temp_image_path}")
                    await update.message.reply_photo(
                        open(temp_image_path, "rb"),
                        caption="Сгенерированное изображение для завершающего кадра"
                    )
                    break
                except Exception as e:
                    logger.error(f"Ошибка генерации завершающего кадра, попытка {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    logger.error(f"Не удалось сгенерировать завершающий кадр после {max_retries} попыток")
                    await update.message.reply_text(
                        f"Не удалось сгенерировать завершающий кадр: {e}."
                    )
                    break

            if generated_image_url:
                try:
                    logger.debug("Вызов Flux API для завершающего кадра")
                    flux_api = self.api_factory.get_api("flux")
                    enhanced_image_url = await flux_api.send_request(
                        prompt=f"Enhance the realism of this image, preserving all background elements, non-clothing details, and textures exactly as they are, maintaining consistent style, lighting, and colors with previous scenes",
                        image_url=generated_image_url,
                        params={
                            "width": 1024,
                            "height": 1536,
                            "model": "ultra",
                            "num_inference_steps": 36,
                            "guidance_scale": 7.5,
                            "strength": 0.3,
                            "is_sync": False,
                            "preserve_background": True
                        }
                    )
                    logger.info(f"Завершающий кадр улучшен: {enhanced_image_url}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(enhanced_image_url) as response:
                            if response.status != 200:
                                raise Exception(f"Failed to download enhanced final frame: {response.status}")
                            temp_enhanced_path = f"temp/enhanced_{user_id}_final_frame.png"
                            with open(temp_enhanced_path, "wb") as f:
                                content = await response.read()
                                if not content:
                                    raise ValueError(f"Empty content downloaded for enhanced final frame")
                                f.write(content)
                            # Verify file exists and is not empty
                            if not os.path.exists(temp_enhanced_path) or os.path.getsize(temp_enhanced_path) == 0:
                                raise FileNotFoundError(f"Enhanced final frame file is missing or empty: {temp_enhanced_path}")
                    await update.message.reply_photo(
                        open(temp_enhanced_path, "rb"),
                        caption="Улучшенное изображение для завершающего кадра"
                    )
                except Exception as e:
                    logger.error(f"Ошибка улучшения завершающего кадра: {e}")
                    await update.message.reply_text(
                        f"Ошибка улучшения завершающего кадра: {e}."
                    )

            await update.message.reply_text("Генерирую видео...")
            logger.debug("Вызов Pika API для генерации видео")
            pika_api = self.api_factory.get_api("pika")
            
            # Prepare image paths and prompts
            image_paths = []
            frame_prompts = []
            for scene in range(1, num_scenes + 1):
                enhanced_path = f"temp/enhanced_{user_id}_scene_{scene}.png"
                if os.path.exists(enhanced_path) and os.path.getsize(enhanced_path) > 0:
                    image_paths.append(enhanced_path)
                    frame_prompts.append(prompts.get(f"scene_{scene}_video", user_query))
                else:
                    logger.warning(f"Enhanced image for scene {scene} not found or empty at {enhanced_path}")
            
            final_frame_path = f"temp/enhanced_{user_id}_final_frame.png"
            if os.path.exists(final_frame_path) and os.path.getsize(final_frame_path) > 0:
                image_paths.append(final_frame_path)
            else:
                logger.warning(f"Final frame image not found or empty at {final_frame_path}")
            
            # Validate inputs
            if len(image_paths) < 2:
                logger.error(f"Недостаточно изображений для генерации видео: found {len(image_paths)} images")
                await update.message.reply_text("Недостаточно изображений для генерации видео. Требуется хотя бы два изображения.")
                self.telegram_handler.cleanup_temp_files(user_id)
                return

            # Align parameters with testpika.py
            total_duration = num_scenes*5
            num_transitions = len(image_paths) - 1
            frame_durations = [total_duration // num_transitions] * num_transitions

            pika_params = {
                "frame_durations": frame_durations,
                "frame_prompts": frame_prompts,
                "resolution": "1080p",
                "content_type": "pikaframes",
                "loop": "false",
                "model": "2.2",
                "options": {
                    "aspectRatio": 0.5625,
                    "frameRate": 24,
                    "camera": {},
                    "parameters": {
                        "guidanceScale": 12,
                        "motion": 1,
                        "negativePrompt": ""
                    }
                }
            }
            
            logger.debug(f"Calling PikaAPI.send_request with image_paths={image_paths}, prompt={user_query}, params={pika_params}")
            video_path = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Ensure files are accessible
                    for path in image_paths:
                        if not os.path.exists(path):
                            raise FileNotFoundError(f"Image file not found: {path}")
                        with open(path, "rb") as f:
                            content = f.read()
                            if not content:
                                raise ValueError(f"Image file is empty: {path}")
                    
                    # Run synchronous PikaAPI.send_request in a thread
                    video_path = await asyncio.to_thread(
                        pika_api.send_request,
                        image_paths=image_paths,
                        prompt=user_query,
                        params=pika_params,
                        output_path=f"temp/final_video_{user_id}.mp4"
                    )
                    logger.info(f"Видео сгенерировано на попытке {attempt + 1}: {video_path}")
                    
                    # Verify the video file exists
                    if not video_path or not isinstance(video_path, str) or not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
                        raise ValueError(f"Invalid or empty video path returned: {video_path}")
                    
                    # Send the video to the user
                    with open(video_path, "rb") as video_file:
                        await update.message.reply_video(
                            video_file,
                            caption="Сгенерированное видео на основе ваших фото и запроса!"
                        )
                    break
                except Exception as e:
                    logger.error(f"Ошибка генерации видео на попытке {attempt + 1}/{max_retries}: {e}", exc_info=True)
                    if attempt < max_retries - 1:
                        logger.info(f"Повторная попытка через {2 ** attempt} секунд...")
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"Не удалось сгенерировать видео после {max_retries} попыток")
                        await update.message.reply_text(f"Не удалось сгенерировать видео: {e}")
                        break
                finally:
                    await asyncio.sleep(3)
                    logger.debug(f"Очистка временных файлов для user_id={user_id}")
                    for retry in range(2):
                        try:
                            self.telegram_handler.cleanup_temp_files(user_id)
                            break
                        except PermissionError as e:
                            logger.warning(f"Не удалось удалить файлы на попытке {retry + 1}: {e}")
                            await asyncio.sleep(5)
                        except Exception as e:
                            logger.error(f"Ошибка очистки: {e}")
                            break

        except Exception as e:
            logger.error(f"Ошибка обработки: {e}", exc_info=True)
            await update.message.reply_text(f"Произошла ошибка: {e}")

    async def main(self) -> None:
        logger.debug("Инициализация приложения Telegram")
        request = HTTPXRequest(
            connection_pool_size=10,
            connect_timeout=30.0,
            read_timeout=30.0,
        )
        application = Application.builder().token(TOKEN).request(request).build()

        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_message))

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Попытка инициализации Telegram бота, попытка {attempt + 1}/{max_retries}")
                await application.initialize()
                break
            except TimedOut as e:
                logger.error(f"Ошибка таймаута при инициализации: {e}")
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    logger.info(f"Повторная попытка через {delay} секунд...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Не удалось инициализировать бота после всех попыток")
                    raise Exception("Не удалось запустить бота: превышен лимит попыток подключения к Telegram API")
        
        await application.start()
        await application.updater.start_polling()
        logger.info("Bot polling started")
        await asyncio.Event().wait()