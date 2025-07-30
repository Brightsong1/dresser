import asyncio
from bot import Bot

if __name__ == "__main__":
    print("Бот запускается...")
    bot = Bot()
    asyncio.run(bot.main())