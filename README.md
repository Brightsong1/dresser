# Telegram Image-to-Video Generation Bot

This project is a Telegram bot that enables users to send one or multiple photos with an optional caption to generate a video. The bot processes the images using various APIs, enhances them for realism, generates detailed prompts with OpenAI, and creates a video with smooth transitions using the Pika API. The bot ensures consistency in style, lighting, and background across all generated content, delivering a cohesive narrative.

## Project Structure

The project is modular, with each file handling specific responsibilities:

- **`api_params.py`**: Defines parameter classes (`GptImageParams`, `FluxParams`, `KlingParams`) for configuring API requests.
- **`gpt_image_api.py`**: Implements the `GptImageAPI` class for generating photorealistic images using the `gpt-image-1` model.
- **`flux_api.py`**: Implements the `FluxAPI` class for enhancing image realism while preserving details.
- **`kling_api.py`**: Implements the `KlingAPI` class for video generation (though less utilized in the main workflow).
- **`pika_api.py`**: Implements the `PikaAPI` class for generating videos from a sequence of images.
- **`bot.py`**: Contains the core bot logic, handling Telegram interactions, orchestrating API calls, and managing the image-to-video pipeline.
- **`telegram_wrapper.py`**: Utility class for Telegram operations, such as downloading photos and cleaning up temporary files.
- **`retry_util.py`**: Provides a retry mechanism for API requests with timeout handling.
- **`api_factory.py`**: Factory class to instantiate API objects dynamically based on the required service.
- **`api_base.py`**: Abstract base class defining the interface for all API implementations.

## Description

The bot allows users to:

- Send one or more photos with an optional caption (defaults to "Create a video based on these photos" if omitted).
- Process the photos to generate a series of enhanced, photorealistic images using `GptImageAPI` and `FluxAPI`.
- Use OpenAI to create detailed prompts for up to 4 scenes and a final frame, ensuring a cohesive narrative.
- Generate a video from the enhanced images using `PikaAPI`, with smooth transitions and consistent styling.

### Key Features

- **Image Processing**: Generates and enhances images with `GptImageAPI` and `FluxAPI`.
- **Prompt Generation**: Leverages OpenAI to create detailed, narrative-driven prompts for images and videos.
- **Video Creation**: Uses `PikaAPI` to produce a video from processed images, maintaining visual consistency.
- **Asynchronous Operations**: Built with `asyncio` for efficient handling of concurrent tasks.
- **Error Handling**: Includes retries and fallbacks for robust operation.

## Setup and Launch

### Prerequisites

- **Telegram Bot Token**: Obtain from [BotFather](https://core.telegram.org/bots#botfather).
- **API Keys**:
  - OpenAI API key (for prompt generation).
  - GenAPI API key (for `GptImageAPI`, `FluxAPI`, and `KlingAPI`).
  - Pika API credentials (email and password).
- **Python**: Version 3.8 or higher.
- **Dependencies**: Listed in `requirements.txt` (e.g., `aiohttp`, `telegram`, `openai`, `playwright`).



