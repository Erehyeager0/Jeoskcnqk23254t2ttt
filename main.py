from highrise import *
from highrise.models import *
from highrise import BaseBot
from highrise.__main__ import BotDefinition, main as highrise_main
from asyncio import run as arun
from flask import Flask
from threading import Thread

from emotes import*
from kiy import (
    item_hairfront,
    item_hairback,
    item_facehair,
    item_eyebrow,
    item_eye,
    item_nose,
    item_mouth,
    item_shirt,
    item_bottom,
    item_shoes,
    item_accessory,
    item_freckle
)
import random
import asyncio
import time
import importlib
import json
import os
from datetime import datetime

# Create emote_mapping dictionary from emote_list
# Create emote_mapping dictionary from emote_list
emote_mapping = {}
secili_emote = {}
paid_emotes = {}

for emote_data in emote_list:
    aliases, emote_id, duration = emote_data
    # Use first alias as the main key
    main_key = aliases[0].lower()
    emote_info = {"value": emote_id, "time": duration}

    # Add all aliases to emote_mapping
    for alias in aliases:
        emote_mapping[alias.lower()] = emote_info

    # Add to secili_emote (appears to be used for random selection)
    secili_emote[main_key] = emote_info

    # Add to paid_emotes as well
    paid_emotes[main_key] = emote_info

class Bot(BaseBot):
    def __init__(self):
        super().__init__()
        self.emote_looping = False
        self.user_emote_tasks = {}
        self.user_emote_loops = {}
        self.loop_task = None
        self.is_teleporting_dict = {}
        self.following_user = None
        self.following_user_id = None
        self.kus = {}
        self.user_positions = {} 
        self.position_tasks = {}
        self.kat_positions = {}
        self.kat_positions_file = "kat_positions.json"
        self.load_kat_positions()

    haricler = ["","","","","","",","]

    def load_kat_positions(self):
        self.kat_positions = {}
        if os.path.exists(self.kat_positions_file):
            try:
                with open(self.kat_positions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name, pos in data.items():
                        self.kat_positions[name] = Position(
                            x=pos["x"],
                            y=pos["y"],
                            z=pos["z"],
                            facing=pos.get("facing", "FrontRight")  # facing yoksa varsayılan
                        )
                print("✅ Kat pozisyonları yüklendi.")
            except Exception as e:
                print(f"⚠️ Kat pozisyonları yüklenirken hata: {e}")
        else:
            print("📁 Kat pozisyon dosyası bulunamadı, yeni dosya oluşturulacak.")

    def save_kat_positions(self):
        try:
            with open(self.kat_positions_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        name: {
                            "x": pos.x,
                            "y": pos.y,
                            "z": pos.z,
                            "facing": pos.facing
                        }
                        for name, pos in self.kat_positions.items()
                    },
                    f,
                    ensure_ascii=False,
                    indent=4
                )
            print("💾 Kat pozisyonları kaydedildi.")
        except Exception as e:
            print(f"❌ Kat pozisyonları kaydedilirken hata: {e}")

    async def on_emote(self, user: User, emote_id: str, receiver: User | None) -> None:
        print(f"{user.username} emote gönderdi: {emote_id}")

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        self.user_id = session_metadata.user_id  # Botun kendi ID'sini kaydet
        print("Emote botu başarıyla bağlandı ✅")

        await self.highrise.tg.create_task(
            self.highrise.teleport(session_metadata.user_id, Position(4, 0, 4, "FrontRight"))
        )

    async def on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        await self.highrise.chat(f"@{user.username},🔥Marjinal Club'a🔥 Hoşgeldin!")
        try:
            emote_name = random.choice(list(secili_emote.keys()))
            emote_info = secili_emote[emote_name]
            emote_to_send = emote_info["value"]
            await self.highrise.send_emote(emote_to_send, user.id)
        except Exception as e:
            print(f"Kullanıcıya emote gönderilirken hata oluştu {user.id}: {e}")

    async def on_user_leave(self, user: User):
        user_id = user.id
        farewell_message = f"Hoşça kal @{user.username}, yine bekleriz 🙏🏻👋🏻"
        if user_id in self.user_emote_loops:
            await self.stop_emote_loop(user_id)
        await self.highrise.chat(farewell_message)

    async def on_chat(self, user: User, message: str) -> None:
        message = message.strip().lower()

        # Emote başlat / durdur
        if message in emote_mapping:
            await self.start_emote_loop(user.id, message)
            return

        if message == "stop":
            await self.stop_emote_loop(user.id)
            return

        if message.startswith("!botem "):
            emote_name = message[7:].strip()
            if emote_name in emote_mapping:
                await self.start_emote_loop(self.user_id, emote_name)  # Bot kendine emote yapacak
                await self.highrise.send_whisper(user.id, f"Bot '{emote_name}' emote döngüsüne başladı.")
            else:
                await self.highrise.send_whisper(user.id, f"❌ '{emote_name}' isimli emote bulunamadı.")
            return

        if message.startswith("!with "):
            try:
                parts = message.split()
                if len(parts) < 3:
                    await self.highrise.send_whisper(user.id, "❌ Kullanım: !with @kullaniciadi emoteadı")
                    return

                mentioned = parts[1].lstrip("@")
                emote_name = " ".join(parts[2:]).strip()

                # Emote geçerli mi kontrol et
                if emote_name not in emote_mapping:
                    await self.highrise.send_whisper(user.id, f"❌ '{emote_name}' adlı emote bulunamadı.")
                    return

                # Oda kullanıcılarını al
                room_users = await self.highrise.get_room_users()
                target_user = None
                for u, _ in room_users.content:
                    if u.username.lower() == mentioned.lower():
                        target_user = u
                        break

                if not target_user:
                    await self.highrise.send_whisper(user.id, f"❌ @{mentioned} odada bulunamadı.")
                    return

                # Her iki kullanıcıya aynı anda başlat
                await self.start_emote_loop(user.id, emote_name)
                await self.start_emote_loop(target_user.id, emote_name)

                await self.highrise.send_whisper(user.id, f"✅ Sen ve @{mentioned}, '{emote_name}' emote'unu aynı anda yapıyorsunuz.")
                await self.highrise.send_whisper(target_user.id, f"🎭 @{user.username} ile birlikte '{emote_name}' emote'unu yapmaya başladın!")

            except Exception as e:
                await self.highrise.send_whisper(user.id, f"⚠️ Bir hata oluştu: {e}")
            return

        if message.startswith("!all "):
            emote_name = message[5:].strip()

            if emote_name not in emote_mapping:
                await self.highrise.send_whisper(user.id, f"❌ '{emote_name}' adlı emote bulunamadı.")
                return

            emote_data = emote_mapping[emote_name]
            emote_id = emote_data["value"]
            skipped = 0
            started = 0

            room_users = await self.highrise.get_room_users()

            for u, _ in room_users.content:
                if u.username == user.username:
                    continue
                if hasattr(self, "admins") and u.username in self.admins:
                    skipped += 1
                    continue

                try:
                    await self.highrise.send_emote(emote_id, u.id)
                    started += 1
                except Exception as e:
                    print(f"{u.username} için emote başarısız: {e}")

            await self.highrise.send_whisper(user.id, f"✅ {started} kişi '{emote_name}' emote'unu yaptı. {skipped} mod atlandı.")
            return

        if message.startswith("!allloop "):
            emote_name = message[9:].strip()

            if emote_name not in emote_mapping:
                await self.highrise.send_whisper(user.id, f"❌ '{emote_name}' adlı emote bulunamadı.")
                return

            room_users = await self.highrise.get_room_users()
            started = 0
            skipped = 0

            for u, _ in room_users.content:
                if u.username == user.username:
                    continue
                if hasattr(self, "admins") and u.username in self.admins:
                    skipped += 1
                    continue

                try:
                    await self.start_emote_loop(u.id, emote_name)
                    started += 1
                except Exception as e:
                    print(f"{u.username} için emote loop başlatılamadı: {e}")

            await self.highrise.send_whisper(user.id, f"🔁 {started} kişi için '{emote_name}' emote loop'u başlatıldı. {skipped} mod atlandı.")
            return

        if message.lower().startswith("!ceza") and await self.is_user_allowed(user):
            target_username = message.split("@")[-1].strip().lower()
            if target_username not in self.haricler:
                room_users = (await self.highrise.get_room_users()).content
                target_user = next((u for u, _ in room_users if u.username.lower() == target_username), None)

                if target_user:
                    if target_user.id not in self.is_teleporting_dict:
                        self.is_teleporting_dict[target_user.id] = True
                        try:
                            while self.is_teleporting_dict.get(target_user.id, False):
                                random_pos = Position(
                                    random.randint(0, 30), 
                                    random.randint(0, 0), 
                                    random.randint(0, 30)
                                )
                                await self.highrise.teleport(target_user.id, random_pos)
                                await asyncio.sleep(1)
                        except Exception as e:
                            print(f"Teleport sırasında hata: {e}")

                        self.is_teleporting_dict.pop(target_user.id, None)
                        final_pos = Position(17.0, 0.0, 13.5, "FrontRight")
                        await self.highrise.teleport(target_user.id, final_pos)

        if message.lower().startswith("!dur") and await self.is_user_allowed(user):
            target_username = message.split("@")[-1].strip().lower()

            room_users = (await self.highrise.get_room_users()).content
            target_user = next((u for u, _ in room_users if u.username.lower() == target_username), None)

            if target_user:
                self.is_teleporting_dict.pop(target_user.id, None)
                await self.highrise.chat(f"@{target_username} üzerindeki ceza durduruldu.")
            else:
                await self.highrise.chat(f"Kullanıcı @{target_username} odada bulunamadı.")

        if message.lower().startswith("!cak") and await self.is_user_allowed(user):
            target_username = message.split("@")[-1].strip()
            room_users = (await self.highrise.get_room_users()).content
            user_info = next((info for info in room_users if info[0].username.lower() == target_username.lower()), None)

            if user_info:
                target_user_obj, initial_position = user_info

                async def reset_target_position(target_user_obj, initial_position):
                    try:
                        while True:
                            room_users = await self.highrise.get_room_users()
                            current_position = next(
                                (pos for u, pos in room_users.content if u.id == target_user_obj.id), None)

                            if current_position and current_position != initial_position:
                                await self.highrise.teleport(target_user_obj.id, initial_position)
                            await asyncio.sleep(1)
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        print(f"Pozisyon izleme hatası: {e}")

                task = asyncio.create_task(reset_target_position(target_user_obj, initial_position))
                if target_user_obj.id not in self.position_tasks:
                    self.position_tasks[target_user_obj.id] = []
                self.position_tasks[target_user_obj.id].append(task)

                await self.highrise.chat(f"@{target_username} sabit pozisyona kilitlendi.")
            else:
                await self.highrise.chat(f"Kullanıcı @{target_username} odada değil.")

        if message.lower().startswith("!cek") and await self.is_user_allowed(user):
            target_username = message.split("@")[-1].strip().lower()

            room_users = (await self.highrise.get_room_users()).content
            target_user_obj = next((u for u, _ in room_users if u.username.lower() == target_username), None)

            if target_user_obj:
                tasks = self.position_tasks.pop(target_user_obj.id, [])
                for task in tasks:
                    task.cancel()
                await self.highrise.chat(f"@{target_username} pozisyon kilitleme iptal edildi.")
            else:
                await self.highrise.chat(f"Kullanıcı @{target_username} odada bulunamadı.")

        if message.lower().startswith("!kick") and await self.is_user_allowed(user):
            parts = message.split()
            if len(parts) != 2:
                return
            username = parts[1]
            if username.startswith("@"):
                username = username[1:]

            room_users = (await self.highrise.get_room_users()).content
            user_id = None
            for room_user, _ in room_users:
                if room_user.username.lower() == username.lower():
                    user_id = room_user.id
                    break

            if user_id is None:
                await self.highrise.chat(f"Kullanıcı @{username} bulunamadı.")
                return

            try:
                await self.highrise.moderate_room(user_id, "kick")
                await self.highrise.chat(f"@{username} odaya atıldı.")
            except Exception as e:
                print(f"Kick işlemi başarısız: {e}")
                return

        # Kıyafet değiştir
        if message.startswith("degistir"):
            hair_active_palette = random.randint(0, 82)
            skin_active_palette = random.randint(0, 88)
            eye_active_palette = random.randint(0, 49)
            lip_active_palette = random.randint(0, 58)

            outfit = [
                Item(type='clothing', amount=1, id='body-flesh', account_bound=False, active_palette=skin_active_palette),
                Item(type='clothing', amount=1, id=random.choice(item_shirt), account_bound=False, active_palette=-1),
                Item(type='clothing', amount=1, id=random.choice(item_bottom), account_bound=False, active_palette=-1),
                Item(type='clothing', amount=1, id=random.choice(item_accessory), account_bound=False, active_palette=-1),
                Item(type='clothing', amount=1, id=random.choice(item_shoes), account_bound=False, active_palette=-1),
                Item(type='clothing', amount=1, id=random.choice(item_freckle), account_bound=False, active_palette=-1),
                Item(type='clothing', amount=1, id=random.choice(item_eye), account_bound=False, active_palette=eye_active_palette),
                Item(type='clothing', amount=1, id=random.choice(item_mouth), account_bound=False, active_palette=lip_active_palette),
                Item(type='clothing', amount=1, id=random.choice(item_nose), account_bound=False, active_palette=-1),
                Item(type='clothing', amount=1, id=random.choice(item_hairback), account_bound=False, active_palette=hair_active_palette),
                Item(type='clothing', amount=1, id=random.choice(item_hairfront), account_bound=False, active_palette=hair_active_palette),
                Item(type='clothing', amount=1, id=random.choice(item_eyebrow), account_bound=False, active_palette=hair_active_palette)
            ]
            await self.highrise.set_outfit(outfit=outfit)
            return

        # Bot kendini kullanıcıya ışınlar
        if message == "!bot" and await self.is_user_allowed(user):
            try:
                room_users = await self.highrise.get_room_users()
                for u, pos in room_users.content:
                    if u.id == user.id:
                        await self.highrise.teleport(self.user_id, pos)
                        break
            except Exception as e:
                print(f"Bot teleport hatası: {e}")
            return

        # Hazır konumlar
        ready_locations = {
            "": Position(7, 0, 13),
            "": Position(17, 9, 13),
            "": Position(7, 8, 13),
            "": Position(4, 16, 2),
        }

        if message in ready_locations:
            try:
                await self.highrise.teleport(user.id, ready_locations[message])
            except Exception as e:
                print(f"Teleport hatası: {e}")
            return

        # Yetkili kullanıcı mı kontrolü
        if await self.is_user_allowed(user):
            if message.startswith("!tp "):
                parts = message.split()
                if len(parts) >= 2:
                    target_username = parts[1].lstrip("@")
                    target_location = parts[2] if len(parts) > 2 else None

                room_users = await self.highrise.get_room_users()
                target_user = next((u for u, _ in room_users.content if u.username.lower() == target_username.lower()), None)

                if not target_user:
                    await self.highrise.send_whisper(user.id, f"❌ {target_username} odada bulunamadı.")
                elif target_location and target_location in self.kat_positions:
                    await self.highrise.teleport(target_user.id, self.kat_positions[target_location])
                    await self.highrise.send_whisper(user.id, f"✅ {target_username}, '{target_location}' konumuna ışınlandı.")
                    if target_user.id != self.user_id:
                        await self.highrise.send_whisper(target_user.id, f"📍 {user.username} seni '{target_location}' konumuna ışınladı.")
                else:
                    target_pos = next((pos for u, pos in room_users.content if u.username.lower() == target_username.lower()), None)
                    if target_pos:
                        await self.highrise.teleport(user.id, target_pos)
                        await self.highrise.send_whisper(user.id, f"✅ {target_username} kullanıcısına ışınlandın.")
                    else:
                        await self.highrise.send_whisper(user.id, f"❌ {target_username} kullanıcısının pozisyonu alınamadı.")
            else:
                await self.highrise.send_whisper(user.id, "⚠️ Kullanım: !tp @kullanıcı [konum]")
            return
        

            elif message.startswith("!gel "):
                target_username = message[5:].strip().lstrip("@")
                room_users = await self.highrise.get_room_users()
                target_user = next((u for u, _ in room_users.content if u.username.lower() == target_username.lower()), None)

                if target_user:
                    user_pos = next((pos for u, pos in room_users.content if u.id == user.id), None)
                    if user_pos:
                        await self.highrise.teleport(target_user.id, user_pos)
                    await self.highrise.send_whisper(user.id, f"✅ {target_username} yanına ışınlandı.")
                    # Don't whisper to the bot itself
                    if target_user.id != self.user_id:
                        await self.highrise.send_whisper(target_user.id, f"📍 {user.username} seni yanına ışınladı.")
                else:
                    await self.highrise.send_whisper(user.id, f"❌ {target_username} odada bulunamadı.")
                return

            elif message.startswith("!goto "):
                loc = message[6:].strip().lower()
                if loc in ready_locations:
                    await self.highrise.teleport(user.id, ready_locations[loc])
                    await self.highrise.send_whisper(user.id, f"✅ '{loc}' konumuna ışınlandın.")
                else:
                    await self.highrise.send_whisper(user.id, f"❌ '{loc}' konumu bulunamadı.")
                return

            elif message.startswith("!bringall "):
                hedef = message[10:].strip().lower()

                # Eğer hedef hazır konumsa
                if hedef in ready_locations:
                    room_users = await self.highrise.get_room_users()
                    for u, _ in room_users.content:
                        if u.id != self.user_id:  # Bot kendini ışınlamasın
                            try:
                                await self.highrise.teleport(u.id, ready_locations[hedef])
                            except Exception:
                                pass
                    await self.highrise.send_whisper(user.id, f"✅ Tüm kullanıcılar '{hedef}' konumuna taşındı.")

                else:
                    # Kullanıcıya ışınlama modu
                    target_user = None
                    room_users = await self.highrise.get_room_users()
                    for u, pos in room_users.content:
                        if u.username.lower() == hedef and u.id != self.user_id:
                            target_user = (u, pos)
                            break

                    if target_user:
                        for u, _ in room_users.content:
                            if u.id != self.user_id and u.id != target_user[0].id:
                                try:
                                    await self.highrise.teleport(u.id, target_user[1])
                                except Exception:
                                    pass
                        await self.highrise.send_whisper(user.id, f"✅ Tüm kullanıcılar {target_user[0].username} kullanıcısının yanına taşındı.")
                    else:
                        await self.highrise.send_whisper(user.id, f"❌ '{hedef}' konumu veya kullanıcı bulunamadı.")
                return

            elif message.startswith("!say "):
                text = message[5:].strip()
                if text:
                    await self.highrise.chat(text)
                else:
                    await self.highrise.send_whisper(user.id, "⚠️ Boş mesaj gönderilemez.")
                return

            elif message in ["-helpmod", "!helpmod"]:
                await self.highrise.send_whisper(user.id,
                    "🛠️ **Mod Komutları (1/4):**\n"
                    "🧍 `!tp @kullanıcı` → Ona ışınlan.\n"
                    "📍 `!tp @kullanıcı konum` → Hazır konuma ışınla.\n"
                    "📥 `!gel @kullanıcı` → Onu yanına ışınla.\n"
                    "🗺️ `!goto konum` → Kendini hazır konuma ışınla.")

                await self.highrise.send_whisper(user.id,
                    "🛠️ **Mod Komutları (2/4):**\n"
                    "📦 `!bringall konum/@kişi` → Herkesi ışınla.\n"
                    "🤝 `!with @kullanıcı emote` → Belirttiğin kişiyle aynı anda emoji yapar.\n"
                    "🤖 `!bot` → Bot kendini sana ışınlar.\n"
                    )

                await self.highrise.send_whisper(user.id,
                    "🛠️ **Mod Komutları (3/4):**\n"
                    "🚫 `!ceza @kişi` → Sürekli ışınla (ceza).\n"
                    "✅ `!dur @kişi` → Cezayı durdurur.\n"
                    "🧱 `!cak @kişi` → Yerini sabitler.\n"
                    "💨 `!cek @kişi` → Sabitlemeyi iptal eder.")

                await self.highrise.send_whisper(user.id,
                    "🛠️ **Mod Komutları (4/4):**\n"
                    "🦶 `!kick @kişi` → Odadan at.\n"
                                                           "👥 `!all` → Odadaki herkese emoji yap.\n"
                                
    "🔁 `!allloop` → Herkese döngülü emoji başlatır.\n"
                    "ℹ️ `!helpmod` → Bu listeyi tekrar gösterir.")
                return

        else:
            # Yetkisiz kullanıcı komut denediğinde uyar
            restricted_cmds = [
                "!tp", "!gel", "!kick", "!ban", "!unban", "!mute", "!unmute",
                "!promote", "!demote", "!announce", "!say", "!bringall", "!goto", "!listbans"
            ]
            if any(message.startswith(cmd) for cmd in restricted_cmds):
                await self.highrise.send_whisper(user.id, "❌ Bu komutu kullanmak için yetkin yok.")

if message.startswith("!kat "):
            parts = message.split()
            if len(parts) == 2:
                kat_adi = parts[1]
                user_pos = await self.highrise.get_position(user.id)
                self.kat_positions[kat_adi] = Position(
                    x=user_pos.x,
                    y=user_pos.y,
                    z=user_pos.z,
                    facing=user_pos.facing
                )
                self.save_kat_positions()
                self.load_kat_positions()  # Belleğe tekrar yükle
                await self.highrise.send_whisper(user.id, f"✅ '{kat_adi}' adlı kat konumu kaydedildi.")
            else:
                await self.highrise.send_whisper(user.id, "⚠️ Kullanım: !kat k1")
            return

        # !katsil komutu ile pozisyon sil (Sadece admin)
        if message.startswith("!katsil "):
            if not await self.is_user_allowed(user):
                await self.highrise.chat(f"🚫 Bu komutu kullanamazsın @{user.username}.")
                return

            silinecek_kat = message[8:].strip()
            if silinecek_kat in self.kat_positions:
                del self.kat_positions[silinecek_kat]
                self.save_kat_positions()
                await self.highrise.chat(f"🗑️ '{silinecek_kat}' pozisyonu silindi.")
            else:
                await self.highrise.chat(f"❓ '{silinecek_kat}' adlı pozisyon bulunamadı.")
            return

        # !katlar komutu ile tüm pozisyonları listele (Herkes kullanabilir)
        if message == "!katlar":
            if not self.kat_positions:
                await self.highrise.chat("📭 Kayıtlı hiç pozisyon yok.")
            else:
                liste = "\n".join(f"📍 {k}" for k in self.kat_positions.keys())
                await self.highrise.chat(f"📦 Kayıtlı pozisyonlar:\n{liste}")
            return

        # Direkt kat ismi ile ışınlanma (Herkes için)
        if message in self.kat_positions:
            pos = self.kat_positions[message]
            try:
                await self.highrise.teleport(user.id, pos)
                await self.highrise.chat(f"🚀 @{user.username}, '{message}' konumuna ışınlandın!")
            except Exception as e:
                await self.highrise.chat(f"⚠️ Işınlanırken hata oluştu: {e}")
            return

    async def on_whisper(self, user: User, message: str) -> None:
        if await self.is_user_allowed(user):
            # Yetkiliyse odaya mesajı gönder
            await self.highrise.chat(message)

            isimler1 = [
                "\n1 - ",
                "\n2 - ",
                "\n3 - ",
                "\n4 - ",
                "\n5 - ",
            ]
            isimler2 = [
                "\n6 - ",
                "\n7 - ",
                "\n8 - ",
                "\n9 - ",
                "\n10 - ",
            ]
            isimler3 = [
                "\n11 - ",
                "\n12 - ",
                "\n13 - ",
                "\n14 - ",
                "\n15 - ",
            ]
            isimler4 = [
                "\n16 - ",
                "\n17 - ",
                "\n18 - ",
                "\n19 - ",
                "\n20 - ",
            ]
            isimler5 = [
                "\n21 - ",
                "\n22 - ",
                "\n23 - ",
                "\n24 - ",
                "\n25 - ",
                "\n26 - "
            ]


            if message.lower().startswith("banlist"):
                  await self.highrise.chat("\n".join(isimler1))
                  await self.highrise.chat("\n".join(isimler2))
                  await self.highrise.chat("\n".join(isimler3))
                  await self.highrise.chat("\n".join(isimler4))
                  await self.highrise.chat("\n".join(isimler5))
                  await self.highrise.chat(f"\n\nBot sahibini takip edin: @Carterers")

    async def start_emote_loop(self, user_id: str, emote_name: str) -> None:
        if user_id in self.user_emote_tasks:
            current_task = self.user_emote_tasks[user_id]
            if not current_task.done():
                if getattr(current_task, "emote_name", None) == emote_name:
                    return  # Aynı emote zaten çalışıyor
                else:
                    current_task.cancel()
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass
            self.user_emote_tasks.pop(user_id, None)

        task = asyncio.create_task(self._emote_loop(user_id, emote_name))
        task.emote_name = emote_name
        self.user_emote_tasks[user_id] = task

    # Emote döngüsünü gerçekleştiren iç task
    async def _emote_loop(self, user_id: str, emote_name: str) -> None:
        if emote_name not in emote_mapping:
            return
        emote_info = emote_mapping[emote_name]
        emote_to_send = emote_info["value"]
        emote_time = emote_info["time"]

        while True:
            try:
                await self.highrise.send_emote(emote_to_send, user_id)
            except Exception as e:
                if "Target user not in room" in str(e):
                    print(f"{user_id} odada değil, emote gönderme durduruluyor.")
                    break
            await asyncio.sleep(emote_time)

    # Emote döngüsünü durdur
    async def stop_emote_loop(self, user_id: str) -> None:
        if user_id in self.user_emote_tasks:
            task = self.user_emote_tasks[user_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self.user_emote_tasks.pop(user_id, None)

    async def is_user_allowed(self, user: User) -> bool:
        user_privileges = await self.highrise.get_room_privilege(user.id)
        return user_privileges.moderator or user.username in ["Carterers", "Batuhan_03a"]

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem | Item) -> None:
        message = f"{sender.username} tarafından {receiver.username} adlı kişiye {tip.amount} miktarında hediye gönderildi! 🎁 Teşekkürler!"
        await self.highrise.chat(message)

    async def run(self, room_id, token) -> None:
        from highrise import BotDefinition
        from highrise.__main__ import main as highrise_main
        definitions = [BotDefinition(self, room_id, token)]
        await highrise_main(definitions)

    async def shutdown(self):
        # Task'ları iptal et
        for task in asyncio.all_tasks():
            task.cancel()
        # Cancel edilenleri bekle
        await asyncio.gather(*asyncio.all_tasks(), return_exceptions=True)

class WebServer():
    def __init__(self):
        self.app = Flask(__name__)

        @self.app.route('/')
        def index() -> str:
            return "Bot çalışıyor ✅"

    def run(self) -> None:
        self.app.run(host='0.0.0.0', port=8080)

    def keep_alive(self):
        t = Thread(target=self.run)
        t.start()

# BOT BAŞLATICI
if __name__ == "__main__":
    WebServer().keep_alive()  # 🔁 Web server'ı başlat

    time.sleep(2)

    room_id = "6862d2d8d4ad9540407d076a"
    bot_token = "ccb36486b5686dbc60ac97e550a82ebd475dfd402e84c1ed109f8da74538fefd"
    bot = Bot()

    definitions = [BotDefinition(bot, room_id, bot_token)]
    asyncio.run(highrise_main(definitions))