from pymongo import MongoClient
import os

#----------------------------------------------+
#                 Variables                    |
#----------------------------------------------+
perms_tr = {
    "create_instant_invite": "Создавать приглашения",
    "kick_members": "Кикать участников",
    "ban_members": "Банить участников",
    "administrator": "Администратор",
    "manage_channels": "Управлять каналами",
    "manage_guild": "Управлять сервером",
    "add_reactions": "Добавлять реакции",
    "view_audit_log": "Просматривать журнал аудита",
    "priority_speaker": "Приоритетный режим",
    "stream": "Видео",
    "read_messages": "Читать сообщения",
    "view_channel": "Видеть канал",
    "send_messages": "Отправлять сообщения",
    "send_tts_messages": "Отправлять TTS сообщения",
    "manage_messages": "Управлять сообщениями",
    "embed_links": "Встраивать ссылки",
    "attach_files": "Прикреплять файлы",
    "read_message_history": "Просматривать историю сообщений",
    "mention_everyone": "Упоминать everyone / here",
    "external_emojis": "Использовать внешние эмодзи",
    "view_guild_insights": "View server insights",
    "connect": "Подключаться",
    "speak": "Говорить",
    "mute_members": "Выключать микрофон у участников",
    "deafen_members": "Заглушать участников",
    "move_members": "Перемещать участников",
    "use_voice_activation": "Использовать режим рации",
    "change_nickname": "Изменять никнейм",
    "manage_nicknames": "Управлять никнеймами",
    "manage_roles": "Управлять ролями",
    "manage_permissions": "Управлять правами",
    "manage_webhooks": "Управлять вебхуками",
    "manage_emojis": "Управлять эмодзи"
}
db_token = str(os.environ.get("db_token"))
cluster = MongoClient(db_token)
db = cluster["tournament_tool_db"]

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
def display_perms(missing_perms):
    out = ""
    for perm in missing_perms:
        out += f"> {perms_tr[perm]}\n"
    return out


def vis_aliases(aliases):
    if aliases not in [None, []]:
        out = "**Синонимы:** "
        for a in aliases:
            out += f"`{a}`, "
        return out[:-2]
    else:
        return ""


def carve_int(string):
    digits = [str(i) for i in range(10)]
    out = ""
    for s in string:
        if s in digits:
            out += s
        elif out != "":
            break
    return int(out) if out != "" else None


def is_int(string):
    try:
        int(string)
        return True
    except ValueError:
        return False


def get_field(_dict, *key_wrods, default=None):
    if _dict is not None:
        for kw in key_wrods:
            if kw in _dict:
                _dict = _dict[kw]
            else:
                _dict = None
                break
    return default if _dict is None else _dict


def find_alias(dict_of_aliases, search):
    out, search = None, search.lower()
    for key in dict_of_aliases:
        aliases = dict_of_aliases[key]
        aliases.append(key)
        for al in aliases:
            if al.startswith(search):
                out = key
                break
        if out is not None:
            break
    return out


def antiformat(text):
    alph = "*_`|~"
    out = ""
    for s in str(text):
        if s in alph:
            out += "\\"
        out += s
    return out


def has_permissions(member, perm_array):
    perms_owned = dict(member.guild_permissions)
    total_needed = len(perm_array)
    for perm in perm_array:
        if perms_owned[perm]:
            total_needed -= 1
    return total_needed == 0


async def get_message(channel, msg_id):
    try:
        return await channel.fetch_message(msg_id)
    except Exception:
        return None


class detect:
    @staticmethod
    def member(guild, search):
        ID = carve_int(search)
        if ID is None:
            ID = 0
        member = guild.get_member(ID)
        if member is None:
            member = guild.get_member_named(search)
        return member
    
    @staticmethod
    def channel(guild, search):
        ID = carve_int(search)
        if ID is None:
            ID = 0
        channel = guild.get_channel(ID)
        if channel is None:
            for c in guild.channels:
                if c.name == search:
                    channel = c
                    break
        return channel
    
    @staticmethod
    def role(guild, search):
        ID = carve_int(search)
        if ID is None:
            ID = 0
        role = guild.get_role(ID)
        if role is None:
            for r in guild.roles:
                if r.name == search:
                    role = r
                    break
        return role
    
    @staticmethod
    def user(search, client):
        ID = carve_int(search)
        user = None
        if ID is not None:
            user = client.get_user(ID)
        return user


class Server:
    def __init__(self, discord_guild):
        if isinstance(discord_guild, int):
            self.id = discord_guild
        else:
            self.id = discord_guild.id

    def load_data(self):
        collection = db["config"]
        result = collection.find_one({"_id": self.id})
        return {} if result is None else result

    def get_participants(self):
        collection = db["users"]
        results = collection.find({})
        if results is None:
            return []
        else:
            out = []
            for result in results:
                pts, trs = 0, 0
                for t in result.get("history", []):
                    pts += t["rating"]
                    trs += 1
                out.append((result.get("_id"), pts, trs))
            return out

    def reset_participants(self):
        collection = db["users"]
        collection.delete_many({})

    def get_mod_roles(self):
        collection = db["config"]
        result = collection.find_one(
            {"_id": self.id},
            projection={"mod_roles": True}
        )
        if result is None:
            result = {}
        return result.get("mod_roles", [])

    def get_gameroles(self):
        collection = db["config"]
        result = collection.find_one(
            {"_id": self.id},
            projection={"gameroles": True}
        )
        if result is None:
            result = {}
        return result.get("gameroles", {})

    def add_tournament_channel(self, channel_id: int):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$addToSet": {"tournament_channels": channel_id}},
            upsert=True
        )
    
    def remove_tournament_channel(self, channel_id: int):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$pull": {"tournament_channels": channel_id}}
        )

    def set_log_channel(self, channel_id: int):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {"log_channel": channel_id}},
            upsert=True
        )

    def get_tournament_channels(self):
        collection = db["config"]
        result = collection.find_one(
            {"_id": self.id},
            projection={"tournament_channels": True}
        )
        if result is None:
            result = {}
        return result.get("tournament_channels", [])

    def get_log_channel(self):
        collection = db["config"]
        result = collection.find_one(
            {"_id": self.id},
            projection={"log_channel": True}
        )
        return None if result is None else result.get("log_channel")

    def pull_tournament_channels(self, channels: list):
        collection = db["config"]
        collection.update_one(
            {"_id": self.id},
            {"$pull": {"tournament_channels": {"$in": channels}}}
        )


class VoiceButton:
    def __init__(self, server_id: int, button_id: int, data: dict=None):
        """data = {limit: int, name: str}"""
        self.server_id = server_id
        self.id = int(button_id)
        if data is None:
            # Getting missing data
            collection = db["vc_config"]
            result = collection.find_one(
                {"_id": self.id, f"buttons.{self.id}": {"$exists": True}},
                projection={f"buttons.{self.id}": True}
            )
            if result is None:
                data = {}
            else:
                data = result.get("buttons", {}).get(f"{self.id}", {})
            del result
        
        self.limit = data.get("limit")
        self.name = data.get("name")


class VConfig:
    def __init__(self, _id: int, projection: dict=None):
        self.id = _id
        collection = db["vc_config"]
        result = collection.find_one(
            {"_id": self.id},
            projection=projection
        )
        if result is None:
            result = {}
        self.buttons = [VoiceButton(self.id, ID, data) for ID, data in result.get("buttons", {}).items()]
        self.waiting_room_ids = result.get("waiting_room_ids", [])
        del result
    
    def get(self, _id: int):
        for vb in self.buttons:
            if vb.id == _id:
                return vb
    
    def which_creates(self, limit: int, name: str):
        for button in self.buttons:
            if button.name == name and button.limit == limit:
                return button

    def add_button(self, _id: int, limit: int, name: str):
        data = {
            "limit": limit,
            "name": name
        }
        del limit, name
        collection = db["vc_config"]
        collection.update_one(
            {"_id": self.id},
            {"$set": {f"buttons.{_id}": data}},
            upsert=True
        )
    
    def remove_button(self, _id: int):
        if self.get(_id) is not None:
            collection = db["vc_config"]
            collection.update_one(
                {"_id": self.id},
                {"$unset": {f"buttons.{_id}": ""}},
                upsert=True
            )

    def add_waiting_room(self, _id: int):
        collection = db["vc_config"]
        collection.update_one(
            {"_id": self.id},
            {"$addToSet": {"waiting_room_ids": _id}},
            upsert=True
        )
    
    def remove_waiting_room(self, _id: int):
        collection = db["vc_config"]
        collection.update_one(
            {"_id": self.id},
            {"$push": {"waiting_room_ids": _id}},
            upsert=True
        )


# The end