import os
from dotenv import load_dotenv

# بارگذاری متغیرها از فایل .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID")) # آی‌دی عددی ادمین