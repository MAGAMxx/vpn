import json
import uuid
from datetime import datetime, timedelta

CONFIG_PATH = "/etc/xray/config.json"

def add_user(plan_days):
    user_uuid = str(uuid.uuid4())
    short_id = uuid.uuid4().hex[:8]

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Добавляем в reality clients
    config["inbounds"][0]["settings"]["clients"].append({
        "id": user_uuid,
        "flow": "",
        "short_id": short_id
    })

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    # Перезапуск xray
    import subprocess
    subprocess.run(["systemctl", "restart", "xray"])

    expiry = datetime.now() + timedelta(days=plan_days)
    return user_uuid, short_id, expiry