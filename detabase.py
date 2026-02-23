import sqlite3
import string
import random
from datetime import datetime

class Database:
    def init(self, db_name="movies.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """ایجاد جدول فیلم‌ها"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_code TEXT UNIQUE NOT NULL,  -- کد یکتا برای لینک
                file_id TEXT NOT NULL,
                file_name TEXT,
                caption TEXT,
                views INTEGER DEFAULT 0,
                upload_date TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def generate_unique_code(self, length=6):
        """ساخت یه کد تصادفی یکتا برای هر فایل"""
        characters = string.ascii_letters + string.digits  # حروف و اعداد
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        while True:
            code = ''.join(random.choices(characters, k=length))
            # چک میکنیم ببینیم این کد قبلا استفاده شده یا نه
            cursor.execute("SELECT id FROM files WHERE unique_code = ?", (code,))
            if cursor.fetchone() is None:
                conn.close()
                return code
            # اگه استفاده شده بود، دوباره یه کد می‌سازیم

    def add_file(self, file_id, file_name, caption=""):
        """اضافه کردن فایل جدید و گرفتن کد یکتاش"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        unique_code = self.generate_unique_code()
        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO files (unique_code, file_id, file_name, caption, upload_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (unique_code, file_id, file_name, caption, upload_date))

        conn.commit()
        conn.close()
        return unique_code

    def get_file_by_code(self, unique_code):
        """گرفتن اطلاعات فایل با استفاده از کد یکتا (برای وقتی کاربر لینک رو زد)"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM files WHERE unique_code = ?', (unique_code,))
        file = cursor.fetchone()
        if file:
            # افزایش تعداد بازدید
            cursor.execute('UPDATE files SET views = views + 1 WHERE unique_code = ?', (unique_code,))
            conn.commit()
        conn.close()
        return file

    def get_all_files(self):
        """گرفتن لیست همه فایل‌ها (برای ادمین)"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT unique_code, file_name, views, upload_date FROM files ORDER BY upload_date DESC")
        files = cursor.fetchall()
        conn.close()
        return files