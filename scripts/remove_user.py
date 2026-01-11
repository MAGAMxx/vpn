import json
import sqlite3
from datetime import datetime
import subprocess

CONFIG_PATH = "/etc/xray/config.json"

# подключаем БД
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

# читаем конфиг
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# текущая дата
now = datetime.now()

# получаем всех просроченных пользователей
cursor.execute("SELECT tg_id, uuid, short_id, plan, expiry FROM users")
rows = cursor.fetchall()

deleted = 0

for tg_id, user_uuid, short_id, plan, expiry_str in rows:
    expiry = datetime.fromisoformat(expiry_str)
    if now >= expiry:
        # удаляем из конфига
        clients = config["inbounds"][0]["settings"]["clients"]
        clients = [c for c in clients if c.get("id") != user_uuid]
        config["inbounds"][0]["settings"]["clients"] = clients

        # удаляем из БД
        cursor.execute("DELETE FROM users WHERE tg_id=? AND uuid=?", (tg_id, user_uuid))
        deleted += 1

# сохраняем конфиг
with open(CONFIG_PATH, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

# перезапускаем xray
if deleted > 0:
    subprocess.run(["systemctl", "restart", "xray"])
    print(f"Удалено {deleted} просроченных пользователей")
