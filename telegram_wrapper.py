import os
import aiohttp
from telegram import PhotoSize
from key import TOKEN

class TelegramHandler:
    def __init__(self):
        self.temp_dir = "temp"
        os.makedirs(self.temp_dir, exist_ok=True)

    async def download_photo(self, photo: PhotoSize, user_id: int) -> str:
        file = await photo.get_file()
        path = os.path.join(self.temp_dir, f"{user_id}.jpg")
        await file.download_to_drive(path)
        return path

    def cleanup_temp_files(self, user_id: int, num_scenes: int = 4) -> None:
        paths = [
            os.path.join(self.temp_dir, f"{user_id}.jpg"),
            os.path.join(self.temp_dir, f"generated_{user_id}.png"),
            os.path.join(self.temp_dir, f"enhanced_{user_id}.png")
        ]
        for scene in range(1, num_scenes + 1):
            paths.extend([
                os.path.join(self.temp_dir, f"generated_{user_id}_scene_{scene}.png"),
                os.path.join(self.temp_dir, f"enhanced_{user_id}_scene_{scene}.png"),
                os.path.join(self.temp_dir, f"video_{user_id}_scene_{scene}.mp4")
            ])
        paths.append(os.path.join(self.temp_dir, f"generated_{user_id}_final_frame.png"))
        paths.append(os.path.join(self.temp_dir, f"enhanced_{user_id}_final_frame.png"))

        for path in paths:
            if os.path.exists(path):
                os.remove(path)