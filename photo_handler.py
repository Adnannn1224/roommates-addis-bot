import os
from PIL import Image

async def save_photo(photo, user_id, bot):
    os.makedirs('photos', exist_ok=True)
    file = await bot.get_file(photo[-1].file_id)  # ← ADD 'await'
    path = f'photos/{user_id}.jpg'
    await file.download_to_drive(path)  # ← Use async download

    img = Image.open(path)
    img.thumbnail((200, 200))
    thumb = f'photos/{user_id}_thumb.jpg'
    img.save(thumb)
    return thumb