import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import uuid
import requests
import json
import time
import threading
import pytz
import db
from config import 

requests.packages.urllib3.disable_warnings()
bot = telebot.TeleBot(BOT_TOKEN)
session = requests.Session()

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('EuropeMoscow')

# Настройки для Happ + Render
RENDER_URL = httpsmagamix.onrender.com      # ← измени, если subdomain другой
SUB_PATH = sub

# Emoji для оформления
EMOJI = {
    home 🏠, back ↩️, key 🔑, buy 💳, support 🆘,
    time ⏰, link 🔗, copy 📋, check ✅, cross ❌,
    info ℹ️, rocket 🚀, crown 👑, shield 🛡️, wifi 📡,
    lock 🔒, unlock 🔓, star ⭐, fire 🔥, money 💰,
    card 💎, phone 📱, bank 🏦, download 📥, upload 📤,
    speed ⚡, global 🌐, settings ⚙️, friends 👥, gift 🎁,
    invite 📨, stats 📊, trophy 🏆, medal 🏅, party 🎉,
    diamond 💎
}

# Реферальная система
REFERRAL_REWARD_DAYS = 5  # +5 дней за каждого друга

# --- Взаимодействие с 3X-UI ---
def xui_login()
    try
        login_url = f{PANEL_URL}{PANEL_PATH}login
        r = session.post(login_url, data={username PANEL_USER, password PANEL_PASS}, verify=False, timeout=10)
        return r.status_code == 200
    except Exception as e
        print(f[LOGIN ERROR] {e})
        return False


def add_user_to_xray(user_uuid, email, days)
    if not xui_login()
        print([ADD CLIENT] Не удалось авторизоваться)
        return None

    expiry_time = int((time.time() + (days  86400))  1000)
    
    # Генерируем короткий subId (как в панели w794j35f1udoambp)
    sub_id = secrets.token_hex(8)  # 16 символов hex — идеально подходит

   payload = {
       "id": INBOUND_ID,
       "settings": json.dumps({
           "clients": [{
               "id": user_uuid,
               "alterId": 0,
               "email": "MAGAMIX"     email,  # или ваша переменная с email
               "limitIp": 2,
               "totalGB": 150,  # или 0
               "expiryTime": expiry_time,
               "enable": True,
               "tgId": "",
               "subId": sub_id,
               "remark": "⚡ MAGAMIX VPN | Нидерланды"
           }]
       })
   }

    try
        url = f{PANEL_URL}{PANEL_PATH}panelapiinboundsaddClient
        r = session.post(url, json=payload, verify=False, timeout=15)
        response_data = r.json()

        if response_data.get(success)
            print(f[SUCCESS] Ключ создан с subId {sub_id})
            return sub_id  # возвращаем sub_id (короткий токен)
        
        else
            msg = response_data.get(msg, )
            print(f[ADD CLIENT] Ошибка панели {msg})
            return None
    
    except Exception as e
        print(f[ADD CLIENT ERROR] {e})
        return None

def generate_subscription_link(sub_id)
    return f{SUB_BASE_URL}{SUB_PATH}{sub_id}


def update_user_in_xray(email, new_days)
    if not xui_login()
        return False

    try
        url = f{PANEL_URL}{PANEL_PATH}panelapiinboundsget{INBOUND_ID}
        r = session.get(url, verify=False, timeout=10)
        data = r.json()

        if not data.get(success)
            return False

        settings = json.loads(data[obj][settings])
        clients = settings.get(clients, [])

        for client in clients
            if client.get(email) == email
                expiry_time = int((time.time() + (new_days  86400))  1000)
                client[expiryTime] = expiry_time
                break

        payload = {
            id INBOUND_ID,
            settings json.dumps({clients clients})
        }

        update_url = f{PANEL_URL}{PANEL_PATH}panelapiinboundsupdate{INBOUND_ID}
        r = session.post(update_url, json=payload, verify=False, timeout=15)
        return r.json().get(success, False)

    except Exception as e
        print(f[UPDATE CLIENT ERROR] {e})
        return False

def delete_user_from_xray(email)
    if not xui_login()
        return False
    try
        url = f{PANEL_URL}{PANEL_PATH}panelapiinbounds{INBOUND_ID}delClient{email}
        r = session.post(url, verify=False, timeout=10)
        return r.json().get(success, False)
    except Exception as e
        print(f[DEL CLIENT ERROR] {e})
        return False

# --- Вспомогательные функции ---
def generate_vless_link(u_uuid)
    return (fvless{u_uuid}@{SERVER_IP}{SERVER_PORT}type=tcp&encryption=none&security=reality
            f&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F#⚡MAGAMIX_VPN  НИДЕРЛАНДЫ )

def generate_happ_deeplink(sub_id)
    if not sub_id
        return None
    return fhappadd{RENDER_URL}connect{sub_id}

def get_remaining_time_str(end_date)
    end_date_aware = MOSCOW_TZ.localize(end_date)
    now_aware = datetime.datetime.now(MOSCOW_TZ)
    delta = end_date_aware - now_aware
    if delta.total_seconds() = 0
        return истёк
    if delta.days = 1
        return f{delta.days} дн.
    hours = int(delta.total_seconds()  3600) + (1 if delta.total_seconds() % 3600  0 else 0)
    return f{hours} ч.

def generate_referral_link(user_id)
    return fhttpst.me{bot.get_me().username}start=ref{user_id}

def give_referral_reward(referrer_id, referred_id)
    try
        db.cursor.execute(
            SELECT reward_given FROM referrals 
            WHERE referrer_id =  AND referred_id = 
        , (referrer_id, referred_id))
        
        row = db.cursor.fetchone()
        if row and row[0] == 1
            return False
        
        active_key = db.get_active_key(referrer_id)
        
        if active_key
            success = db.extend_key_days(referrer_id, REFERRAL_REWARD_DAYS)
            if success
                uuid_val = active_key[1]
                email = fuser_{referrer_id}_{uuid_val[8]}
                
                new_end_date = active_key[4] + datetime.timedelta(days=REFERRAL_REWARD_DAYS)
                days_until_new_end = (new_end_date - datetime.datetime.now()).days
                
                if days_until_new_end  0
                    update_user_in_xray(email, days_until_new_end)
                
                db.add_referral_reward(referrer_id, referred_id, REFERRAL_REWARD_DAYS)
                
                try
                    bot.send_message(
                        referrer_id,
                        f{EMOJI['party']} Бонус за друга!nn
                        f{EMOJI['gift']} Ваш активный ключ продлен на +{REFERRAL_REWARD_DAYS} дней!n
                        f{EMOJI['friends']} Ваш друг успешно зарегистрировался по вашей ссылке.nn
                        f{EMOJI['trophy']} Приглашайте больше друзей и получайте бонусы!,
                        parse_mode=Markdown
                    )
                except
                    pass
                
                return True
        else
            u_uuid = str(uuid.uuid4())
            email = fref_{referrer_id}_{int(time.time())}
            
            sub_id = add_user_to_xray(u_uuid, email, REFERRAL_REWARD_DAYS)
            if sub_id
                db.add_key(referrer_id, u_uuid, SID, REFERRAL_REWARD_DAYS)
                db.update_key_subid(u_uuid, sub_id)  # ← сохраняем sub_id
                
                try
                    bot.send_message(
                        referrer_id,
                        f{EMOJI['party']} Бонус за друга!nn
                        f{EMOJI['gift']} Вам выдан новый ключ на {REFERRAL_REWARD_DAYS} дней!n
                        f{EMOJI['friends']} Ваш друг успешно зарегистрировался.n
                        f{EMOJI['key']} Ключ в «Мои ключи»nn
                        f{EMOJI['trophy']} Приглашайте больше друзей!,
                        parse_mode=Markdown
                    )
                except
                    pass
                
                return True
        
        return False
    except Exception as e
        print(f[REFERRAL REWARD ERROR] {e})
        return False

def get_main_menu()
    Главное меню
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f{EMOJI['buy']} Купить VPN, callback_data=buy),
        InlineKeyboardButton(f{EMOJI['key']} Мои ключи, callback_data=my_keys)
    )
    kb.add(
        InlineKeyboardButton(f{EMOJI['friends']} Пригласить друга, callback_data=referral),
        InlineKeyboardButton(f{EMOJI['support']} Поддержка, url=httpst.menejnayatp3)
    )
    kb.add(InlineKeyboardButton(f{EMOJI['info']} Информация, callback_data=info))
    return kb

def get_back_button(to=main)
    Кнопка назад
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад, callback_data=fback_{to}))
    return kb

def get_buy_menu()
    Меню покупки с кнопкой назад
    kb = InlineKeyboardMarkup()
    for k, v in PRICES.items()
        kb.add(InlineKeyboardButton(
            f{EMOJI['card']} {v['name']} — {v['price']}₽, 
            callback_data=fplan_{k}
        ))
    kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад, callback_data=back_main))
    return kb

def get_instructions_menu(uuid_key=None)
    Меню инструкций
    kb = InlineKeyboardMarkup()
    if uuid_key
        kb.add(InlineKeyboardButton(
            f{EMOJI['copy']} Скопировать ключ, 
            callback_data=fcopy_{uuid_key}
        ))
    kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад в Мои ключи, callback_data=my_keys))
    kb.add(InlineKeyboardButton(f{EMOJI['home']} В главное меню, callback_data=main))
    return kb

def get_referral_menu(user_id)
    Меню реферальной системы
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Генерируем реферальную ссылку
    ref_link = generate_referral_link(user_id)
    
    # Получаем статистику
    ref_stats = db.get_referrals_stats(user_id)
    
    kb.add(InlineKeyboardButton(
        f{EMOJI['invite']} Скопировать ссылку, 
        callback_data=fcopy_ref_{user_id}
    ))
    
    kb.add(InlineKeyboardButton(
        f{EMOJI['stats']} Моя статистика, 
        callback_data=ref_stats
    ))
    
    kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад, callback_data=back_main))
    kb.add(InlineKeyboardButton(f{EMOJI['home']} В главное меню, callback_data=main))
    
    return kb, ref_link, ref_stats

# --- Обработка команд ---
@bot.message_handler(commands=['start'])
def start_handler(message)
    user_id = message.from_user.id
    username = message.from_user.username

    referrer_id = None
    if len(message.text.split())  1
        ref_code = message.text.split()[1]
        if ref_code.startswith('ref')
            try
                referrer_id = int(ref_code[3])
                if referrer_id == user_id
                    referrer_id = None
            except
                referrer_id = None

    is_new_user = db.add_user(user_id, username, referrer_id)

    if is_new_user and referrer_id
        give_referral_reward(referrer_id, user_id)

    active_key = db.get_active_key(user_id)

    if not active_key
        u_uuid = str(uuid.uuid4())
        email = ftrial_{user_id}_{int(time.time())}

        sub_id = add_user_to_xray(u_uuid, email, 3)
        if sub_id
            db.add_key(user_id, u_uuid, SID, 3)
            db.update_key_subid(u_uuid, sub_id)
            text = (
                f{EMOJI['crown']} Добро пожаловать! {EMOJI['fire']}nn
                f{EMOJI['star']} Триал 3 дня выдан!n
                f{EMOJI['key']} Ключ в «Мои ключи»nn
                f{EMOJI['gift']} Приглашай друзей — +{REFERRAL_REWARD_DAYS} дней!
            )
        else
            text = f{EMOJI['cross']} Ошибка триала
    else
        text = (
            f{EMOJI['crown']} С возвращением! {EMOJI['fire']}nn
            f{EMOJI['rocket']} VPN готов к работе!
        )

    bot.send_message(user_id, text, reply_markup=get_main_menu(), parse_mode=Markdown)

@bot.callback_query_handler(func=lambda call True)
def query_handler(call)
    uid = call.from_user.id
    
    # Обработка кнопки Назад
    if call.data.startswith(back_)
        target = call.data.replace(back_, )
        if target == main
            text = (
                f{EMOJI['crown']} Главное меню MAGAMIX VPN {EMOJI['fire']}nn
                f{EMOJI['info']} Выберите действие
            )
            bot.edit_message_text(text, uid, call.message.id, 
                                 reply_markup=get_main_menu(), parse_mode=Markdown)
        return
    
    if call.data == main
        text = (
            f{EMOJI['crown']} Главное меню MAGAMIX VPN {EMOJI['fire']}nn
            f{EMOJI['info']} Выберите действие
        )
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=get_main_menu(), parse_mode=Markdown)
    
    elif call.data == buy
        text = (
            f{EMOJI['money']} Выберите тарифный план {EMOJI['card']}nn
            f{EMOJI['info']} Все тарифы включаютn
            f• {EMOJI['speed']} Максимальную скоростьn
            f• {EMOJI['shield']} Полную защитуn
            f• {EMOJI['global']} Неограниченный трафикn
            f• {EMOJI['settings']} Круглосуточную поддержкуn
        )
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=get_buy_menu(), parse_mode=Markdown)
    
    elif call.data.startswith(plan_)
        plan_key = call.data.replace(plan_, )
        data = PRICES[plan_key]
        db.add_payment(uid, plan_key)
        
        text = (
            f{EMOJI['card']} Оплата тарифа {data['name']}nn
            f{EMOJI['money']} Сумма к оплате {data['price']}₽n
            f{EMOJI['bank']} Банк для перевода {PAY_BANK}n
            f{EMOJI['phone']} Номер для перевода `{PAY_PHONE}`nn
            f{EMOJI['info']} Инструкцияn
            f1. Переведите {data['price']}₽ на указанный номерn
            f2. Сохраните чек об оплатеn
            f3. Отправьте скриншот чека в этот чатnn
            f{EMOJI['check']} После проверки ключ будет выдан автоматически!
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад к тарифам, callback_data=buy))
        kb.add(InlineKeyboardButton(f{EMOJI['home']} В главное меню, callback_data=main))
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode=Markdown)
    
    elif call.data == my_keys
        keys = db.get_keys(uid)
        active_key = db.get_active_key(uid)

        if not active_key
            text = f{EMOJI['key']} Нет активных ключей {EMOJI['cross']}
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(f{EMOJI['buy']} Купить VPN, callback_data=buy))
            kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад, callback_data=back_main))
            bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode=Markdown)
            return

        u_uuid = active_key[1]
        end_date = active_key[4]

        end_date_aware = MOSCOW_TZ.localize(end_date)
        now_aware = datetime.datetime.now(MOSCOW_TZ)
        delta = end_date_aware - now_aware

        if delta.total_seconds() = 0
            text = f{EMOJI['key']} Ключ истёк {EMOJI['cross']}
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(f{EMOJI['buy']} Купить VPN, callback_data=buy))
            kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад, callback_data=back_main))
            bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode=Markdown)
            return

        remaining = f{delta.days} дн. if delta.days = 1 else f{int(delta.total_seconds()  3600)} ч.

        text = (
            f{EMOJI['key']} Активный ключnn
            f{EMOJI['time']} Осталось {remaining}n
            fДо {end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y %H%M')} МСКnn
            f{EMOJI['info']} Дальше
        )

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            f{EMOJI['copy']} Получить ссылку,
            callback_data=fshow_key_{u_uuid}
        ))
        kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад, callback_data=back_main))
        kb.add(InlineKeyboardButton(f{EMOJI['home']} Главное, callback_data=main))

        bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode=Markdown)
    
    elif call.data.startswith(show_key_)
        u_uuid = call.data.replace(show_key_, )
        db.cursor.execute(SELECT end_date FROM keys WHERE uuid= AND user_id=, (u_uuid, uid))
        row = db.cursor.fetchone()
        if not row
            bot.answer_callback_query(call.id, Ключ не найден)
            return

        end_date = datetime.datetime.fromisoformat(str(row[0]))
        remaining = get_remaining_time_str(end_date)
        end_date_formatted = end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y в %H%M') + ' МСК'

        sub_id = db.get_key_subid(u_uuid)
        if not sub_id
            bot.answer_callback_query(call.id, Подписка не найдена)
            return

        sub_link = generate_subscription_link(sub_id)  # ← ссылка-подписка

        text = (
            f{EMOJI['key']} Детали ключаnn
            f{EMOJI['time']} Осталось {remaining}n
            fДо {end_date_formatted}nn
            fНажмите кнопку ниже — Happ откроется автоматически и добавит подписку с трафиком и сроком!
        )

        kb = InlineKeyboardMarkup()
        deeplink = fhttpsmagamix.onrender.comurlurl=happaddhttpsmagamix.onrender.comconnect{sub_id}
        kb.add(InlineKeyboardButton(Подключиться, url=deeplink))
        #kb.add(InlineKeyboardButton(f{EMOJI['copy']} Скопировать ссылку-подписку, callback_data=fcopy_{u_uuid}))
        kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад, callback_data=back_main))
        #kb.add(InlineKeyboardButton(f{EMOJI['home']} Главное, callback_data=main))

        bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode=Markdown)
    
    elif call.data.startswith(copy_)
        if call.data.startswith(copy_ref_)
            user_id = int(call.data.replace(copy_ref_, ))
            ref_link = generate_referral_link(user_id)
            bot.answer_callback_query(call.id, 
                f✅ Реферальная ссылка скопирована!nn{ref_link}, 
                show_alert=True
            )
        else
            u_uuid = call.data.replace(copy_, )
            sub_id = db.get_key_subid(u_uuid)
            if sub_id
                sub_link = generate_subscription_link(sub_id)
                bot.answer_callback_query(call.id, f✅ Ссылка-подписка скопирована!n{sub_link}, show_alert=True)
            else
                bot.answer_callback_query(call.id, Ссылка не найдена, show_alert=True)
    
    elif call.data == referral
        kb, ref_link, ref_stats = get_referral_menu(uid)
        
        text = (
            f{EMOJI['friends']} Пригласите друга — получите бонус! {EMOJI['gift']}nn
            f{EMOJI['trophy']} Как это работаетn
            f1. Отправьте другу вашу реферальную ссылкуn
            f2. Друг должен нажать на ссылку и зарегистрироватьсяn
            f3. Вы автоматически получаете +{REFERRAL_REWARD_DAYS} дней VPNnn
            f{EMOJI['info']} Условияn
            f• Если у вас есть активный ключ — он продлитсяn
            f• Если ключа нет — создастся новый на {REFERRAL_REWARD_DAYS} днейn
            f• Бонус начисляется за каждого нового пользователяnn
            f{EMOJI['stats']} Ваша статистикаn
            f• Всего приглашено {ref_stats['total']}n
            f• Получено бонусов {ref_stats['rewarded']}n
            f• Всего дней бонусов {ref_stats['rewarded']  REFERRAL_REWARD_DAYS}nn
            f{EMOJI['link']} Ваша реферальная ссылкаn
            f`{ref_link}`nn
            f{EMOJI['party']} Приглашайте друзей и пользуйтесь VPN бесплатно!
        )
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode=Markdown)
    
    elif call.data == ref_stats
        ref_stats = db.get_referrals_stats(uid)
        
        text = (
            f{EMOJI['stats']} Ваша реферальная статистикаnn
            f{EMOJI['friends']} Всего приглашено друзей {ref_stats['total']}n
            f{EMOJI['check']} Получено бонусов {ref_stats['rewarded']}n
            f{EMOJI['gift']} Всего дней бонусов {ref_stats['rewarded']  REFERRAL_REWARD_DAYS}nn
            f{EMOJI['trophy']} Приглашайте больше друзей!n
            fКаждый новый друг = +{REFERRAL_REWARD_DAYS} дней VPNnn
            f{EMOJI['diamond']} Чем больше друзей, тем дольше VPN!
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f{EMOJI['friends']} Вернуться к рефералке, callback_data=referral))
        kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад, callback_data=back_main))
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode=Markdown)
    
    elif call.data == info
        text = (
            f{EMOJI['crown']} MAGAMIX VPN {EMOJI['fire']}nn
            f{EMOJI['rocket']} Лучший VPN для вашей безопасности и свободы!nn
            f{EMOJI['speed']} Наши преимуществаn
            f• Максимальная скорость подключенияn
            f• Полная анонимность в сетиn
            f• Защита от слежки и хакеровn
            f• Доступ к заблокированным сайтамn
            f• Безлимитный трафикn
            f• Поддержка 247nn
            f{EMOJI['gift']} Реферальная программаn
            f• Пригласите друга → получите +{REFERRAL_REWARD_DAYS} днейn
            f• Нет ключа Создастся новый на {REFERRAL_REWARD_DAYS} днейn
            f• Есть ключ Он продлится на {REFERRAL_REWARD_DAYS} днейnn
            f{EMOJI['key']} Как начать пользоватьсяn
            f1. Купите подписку в разделе «Купить VPN»n
            f2. Получите ключ в «Мои ключи»n
            f3. Настройте приложение за 2 минутыn
            f4. Наслаждайтесь свободным интернетом!nn
            f{EMOJI['support']} Техническая поддержка @nejnayatp3
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f{EMOJI['buy']} Купить VPN, callback_data=buy))
        kb.add(InlineKeyboardButton(f{EMOJI['friends']} Пригласить друга, callback_data=referral))
        kb.add(InlineKeyboardButton(f{EMOJI['support']} Поддержка, url=httpst.menejnayatp3))
        kb.add(InlineKeyboardButton(f{EMOJI['back']} Назад, callback_data=back_main))
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode=Markdown)
    
    elif call.data.startswith(adm_ok_)
        if call.from_user.id != ADMIN_ID
            bot.answer_callback_query(call.id, ⛔ Доступ запрещен!)
            return
            
        target_id = int(call.data.split(_)[2])
        plan_key = db.get_last_pending_plan(target_id)
        if not plan_key
            bot.send_message(ADMIN_ID, Нет ожидающих платежей.)
            return
        
        days = PRICES[plan_key]['days']
        u_uuid = str(uuid.uuid4())
        email = fuser_{target_id}_{int(time.time())}
        
        if add_user_to_xray(u_uuid, email, days)
            db.add_key(target_id, u_uuid, SID, days)
            link = generate_vless_link(u_uuid)
            
            success_text = (
                f{EMOJI['check']} Оплата подтверждена!nn
                f{EMOJI['key']} Ваш ключ на {days} днейn
                f`{link}`nn
                f{EMOJI['info']} Инструкцияn
                f1. Скопируйте ссылку вышеn
                f2. Откройте Happ Plus  Hiddifyn
                f3. Нажмите «+» → «Импорт из буфера обмена»n
                f4. Наслаждайтесь VPN! {EMOJI['rocket']}
            )
            
            bot.send_message(target_id, success_text, parse_mode=Markdown)
            
            admin_text = f{EMOJI['check']} Ключ выдан пользователю {target_id}
            bot.edit_message_text(admin_text, ADMIN_ID, call.message.id)
        else
            bot.send_message(ADMIN_ID, f{EMOJI['cross']} Ошибка при связи с API 3X-UI)

# --- Приём чеков ---
@bot.message_handler(content_types=['photo'])
def handle_receipt(message)
    uid = message.from_user.id
    bot.send_message(uid, 
        f{EMOJI['check']} Чек принят!nn
        f{EMOJI['time']} Проверка займет несколько минут.n
        f{EMOJI['info']} После проверки ключ придет автоматически.,
        parse_mode=Markdown
    )
    
    bot.forward_message(ADMIN_ID, message.chat.id, message.id)
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f{EMOJI['check']} Подтвердить оплату, 
                               callback_data=fadm_ok_{uid}))
    
    bot.send_message(ADMIN_ID, 
        f{EMOJI['money']} Новый чек от пользователяnn
        fID {uid}n
        fUsername @{message.from_user.username or 'скрыт'},
        reply_markup=kb,
        parse_mode=Markdown
    )

# --- Очистка просроченных ---
def auto_delete_loop()
    while True
        try
            expired = db.get_all_expired_keys()
            for user_id, u_uuid in expired
                db.cursor.execute(SELECT  FROM keys WHERE uuid = , (u_uuid,))
                row = db.cursor.fetchone()
                if row
                    email = fuser_{user_id}_{u_uuid[8]}
                    
                    deleted = delete_user_from_xray(email)
                    if deleted
                        db.delete_key_by_uuid(u_uuid)
                        try
                            bot.send_message(user_id, 
                                f{EMOJI['cross']} Срок действия ключа истекnn
                                f{EMOJI['info']} Ключ был автоматически удален.n
                                f{EMOJI['buy']} Приобретите новый ключ в разделе «Купить VPN»n
                                f{EMOJI['friends']} Или пригласите друга и получите +{REFERRAL_REWARD_DAYS} дней!,
                                parse_mode=Markdown
                            )
                        except
                            pass
        except Exception as e
            print(f[CLEANUP ERROR] {e})
        time.sleep(1800)

threading.Thread(target=auto_delete_loop, daemon=True).start()

if __name__ == __main__
    print(f{EMOJI['rocket']} Бот запущен {datetime.datetime.now(MOSCOW_TZ)})
    print(f{EMOJI['crown']} MAGAMIX VPN + Happ deeplink готов!)
    bot.infinity_polling()
