import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio
from random import randint

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import has_permissions, antiformat, get_message


def unwrap_isolation(text, s):
    length, wid, i = len(text), len(s), 0
    out = ""
    while i < length:
        if text[i:i + wid] == s:
            i += wid
            while i < length and text[i:i + wid] != s:
                out += text[i]
                i += 1
            out += "\n"
        i += 1
    return out.strip()


def color_from_string(_color):
    Col = discord.Color
    _color = _color.lower()
    if "," in _color:
        rgb = [c.strip() for c in _color.split(",")]
        rgb = [int(c) for c in rgb]
        if len(rgb) < 3 or len(rgb) > 3:
            _color = Col.default()
        else:
            in_range_bools = [(c >= 0 and c < 256) for c in rgb]
            if False in in_range_bools:
                _color = Col.default()
            else:
                _color = Col.from_rgb(*rgb)
    else:
        colors = {
            "green": Col.green(), "dark_green": Col.dark_green(),
            "red": Col.red(), "dark_red": Col.dark_red(),
            "blue": Col.default(), "dark_blue": Col.dark_blue(),
            "magenta": Col.magenta(), "teal": Col.teal(),
            "gold": Col.gold(), "orange": Col.orange(),
            "purple": Col.purple(), "blurple": Col.blurple(),
            "white": Col.from_rgb(255, 255, 255), "black": Col.from_rgb(1, 1, 1)
        }
        if _color not in colors:
            _color = Col.default()
        else:
            _color = colors[_color]
    return _color


def from_hex(string):
    return int(string[1:], 16)


def embed_from_string(text_input):
    # Carving logical parts
    _title = unwrap_isolation(text_input, "==")
    _desc = unwrap_isolation(text_input, "--")
    _color = unwrap_isolation(text_input, "##")
    _image_url = unwrap_isolation(text_input, "&&")
    _thumb_url = unwrap_isolation(text_input, "++")
    # Interpreting some values
    if _title == "" and _desc == "" and _color == "" and _image_url == "" and _thumb_url == "":
        return None
    else:
        _color = color_from_string(_color)

        emb = discord.Embed(
            title=_title,
            description=_desc,
            color=_color
        )
        if _image_url != "":
            emb.set_image(url=_image_url)
        if _thumb_url != "":
            emb.set_thumbnail(url=_thumb_url)
        
        return emb


def is_int(string):
    try:
        int(string)
        return True
    except ValueError:
        return False


class utils(commands.Cog):
    def __init__(self, client):
        self.client = client

    #----------------------------------------------+
    #                   Events                     |
    #----------------------------------------------+
    @commands.Cog.listener()
    async def on_ready(self):
        print(f">> Utils cog is loaded")

    #----------------------------------------------+
    #                  Commands                    |
    #----------------------------------------------+
    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.command(
        aliases=["rand"],
        help="выбирает случайное число в указанном диапазоне",
        brief="Ганица",
        usage="-30 100"
    )
    async def random(self, ctx, *, string):
        nums = string.split()[:2]
        all_ints = True
        for i, num in enumerate(nums):
            if is_int(num):
                nums[i] = int(num)
            else:
                all_ints = False
                break
        if not all_ints:
            p, cmd = ctx.prefix, ctx.command.name
            reply = discord.Embed(
                title="💥 Неверный аргумент",
                description=f"После `{p}{cmd}` должны стоять целые числа",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        else:
            if len(nums) > 1:
                l_num, r_num = nums
            else:
                l_num, r_num = 0, nums[0]
            l_num, r_num = min(l_num, r_num), max(l_num, r_num)
            
            if r_num - l_num > 1E12:
                reply = discord.Embed(
                    title="💥 Превышен лимит",
                    description=f"Разница между границами не должна превышать `10 ^ 12`",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=reply)

            else:
                result = randint(l_num, r_num)
                reply = discord.Embed(
                    title=f"🎲 Случайное число между `{l_num}` и `{r_num}`",
                    description=f"**{result}**",
                    color=from_hex("#ffdead")
                )
                reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
                
                await ctx.send(embed=reply)


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.command(
        help=(
            "создаёт рамку с заголовком, текстом, картинкой и т.п.\n"
            "Что нужно писать, чтобы создавать разные части рамки:\n"
            "> `==Заголовок==` - задаёт заголовок\n"
            "> `--Текст--` - задаёт текстовый блок\n"
            "> `##цвет##` - задаёт цвет (см. ниже)\n"
            "> `&&url_картинки&&` - задаёт большую картинку\n"
            "> `++url_картинки++` - задаёт маленькую картинку\n"
            "**О цвете:** цвет может быть как из списка, так и из параметров RGB\n"
            "В RGB формате между `##` должны идти 3 числа через запятую, например `##23, 123, 123##`\n"
            "Список цветов: `red, dark_red, blue, dark_blue, green, dark_green, gold, teal, magenta, purple, blurple, orange, white, black`"
        ),
        brief="Синтаксис",
        usage=(
            "==Обновление==\n"
            "--Мы добавили роль **Помощник**!--\n"
            "##gold##"
        )
    )
    async def embed(self, ctx, *, text):
        p = ctx.prefix
        if not has_permissions(ctx.author, ["administrator"]):
            reply = discord.Embed(
                title="💢 Недостаточно прав",
                description = (
                    "Требуемые права:\n"
                    "> Администратор"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=str(ctx.author.avatar_url))
            await ctx.send(embed=reply)
        
        else:
            emb = embed_from_string(text)
            if emb is None:
                pass
            else:
                await ctx.send(embed=emb)
                await ctx.message.delete()
                try:
                    await ctx.send(f"{p}embed {antiformat(text)}")
                except Exception:
                    pass
    

    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.command(
        help="редактирует мои рамки (эмбеды)",
        brief="ID_сообщения Текст_для_эмбеда",
        usage="123456789123123123 ==Заголовок== --Текст--"
    )
    async def edit(self, ctx, _id, *, text_input):
        if not has_permissions(ctx.author, ["administrator"]):
            reply = discord.Embed(
                title="💢 Недостаточно прав",
                description = (
                    "Требуемые права:\n"
                    "> Администратор"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=str(ctx.author.avatar_url))
            await ctx.send(embed=reply)
        
        elif not _id.isdigit():
            reply = discord.Embed(
                title="❌ Ошибка",
                description=f"ID должно состоять из цифр.\nВведено: {_id}",
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=str(ctx.author.avatar_url))
            await ctx.send(embed=reply)
        
        else:
            message = await get_message(ctx.channel, int(_id))
            if message is None:
                reply = discord.Embed(
                    title="🔎 Сообщение не найдено",
                    description=f"В этом канале нет сообщения с ID: `{_id}`"
                )
                reply.set_footer(text=str(ctx.author), icon_url=str(ctx.author.avatar_url))
                await ctx.send(embed=reply)
            
            elif message.author.id != self.client.user.id:
                reply = discord.Embed(
                    title="❌ Это не моё сообщение",
                    description="Я не имею права редактировать чужие сообщения",
                    color=discord.Color.dark_red()
                )
                reply.set_footer(text=str(ctx.author), icon_url=str(ctx.author.avatar_url))
                await ctx.send(embed=reply)
            
            else:
                emb = embed_from_string(text_input)
                
                await message.edit(embed=emb)
                try:
                    await ctx.author.send(f"{ctx.prefix}edit {_id} {antiformat(text_input)}")
                except Exception:
                    pass
                await ctx.message.delete()
    
    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(utils(client))