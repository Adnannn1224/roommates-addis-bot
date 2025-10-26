import os
from PIL import Image

def save_photo(photo, user_id, bot):
    os.makedirs('photos', exist_ok=True)
    file = bot.get_file(photo[-1].file_id)
    path = f'photos/{user_id}.jpg'
    file.download(path)

    img = Image.open(path)
    img.thumbnail((200, 200))
    thumb = f'photos/{user_id}_thumb.jpg'
    img.save(thumb)
    return thumb