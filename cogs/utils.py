import discord
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio
from random import randint, shuffle, choice
from datetime import datetime, timedelta
import os
from io import BytesIO

#----------------------------------------------+
#                 Variables                    |
#----------------------------------------------+
mc_memory = {}

#----------------------------------------------+
#                 Functions                    |
#----------------------------------------------+
from functions import has_permissions, antiformat, get_message, find_alias, Server


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


def dt_from_string(string):
    try:
        date, time = string.strip().split()
        day, month = date.split(".")[:2]
        hrs, minutes = time.split(":")[:2]
        now = datetime.utcnow()
        return datetime(now.year, int(month), int(day), int(hrs), int(minutes)) - timedelta(hours=3)
    except Exception:
        return None


def is_guild_moderator():
    def predicate(ctx):
        mod_roles = Server(ctx.guild.id, projection={"mod_roles": True}).mod_roles
        author_role_ids = [r.id for r in ctx.author.roles]
        has = False
        for role_id in mod_roles:
            if role_id in author_role_ids:
                has = True
                break
        if has:
            return True
        else:
            raise IsNotModerator()
    return commands.check(predicate)


class IsNotModerator(commands.CheckFailure):
    pass


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
        help="случайное число",
        description="выбирает случайное число в указанном диапазоне",
        brief="Ганица",
        usage="-30 100" )
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
    @commands.has_permissions(administrator=True)
    @commands.command(
        help="выслать рамку",
        description=(
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
        ) )
    async def embed(self, ctx, *, text):
        p = ctx.prefix
        emb = embed_from_string(text)
        if emb is None:
            pass
        else:
            await ctx.send(embed=emb)
            await ctx.message.delete()
            try:
                await ctx.author.send(f"{p}embed {antiformat(text)}")
            except Exception:
                pass
    

    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.has_permissions(administrator=True)
    @commands.command(
        help="отредактировать рамку",
        description="редактирует мои рамки (эмбеды)",
        brief="ID_сообщения Текст_для_эмбеда",
        usage="123456789123123123 ==Заголовок== --Текст--" )
    async def edit(self, ctx, _id, *, text_input):
        if not _id.isdigit():
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
    

    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.check_any(
        commands.has_permissions(administrator=True),
        is_guild_moderator() )
    @commands.command(
        aliases=["count-messages", "cm"],
        help="посчитать сообщения в какой-то период",
        description="считает кол-во сообщений в указанный период времени",
        brief="дата время - дата время",
        usage="01.01 1:00 - 01.01 4:00" )
    async def count_messages(self, ctx, *, after_before):
        p = ctx.prefix; cmd = str(ctx.invoked_with)

        try:
            after, before = after_before.split("-")
            after = dt_from_string(after)
            before = dt_from_string(before)

        except Exception:
            after = None; before = None

        if None in [after, before]:
            reply = discord.Embed(
                title="❌ Неверный формат",
                description=(
                    "Вероятно Вы допустили ошибку в написании временных меток, вот шаблон:\n"
                    f"> `{p}{cmd} 01.01 1:00 - 01.01 3:00`"
                ),
                color=discord.Color.dark_red()
            )
            reply.set_footer(text=str(ctx.author), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=reply)
        
        else:
            if after > before:
                before, after = after, before
            
            await ctx.send("🕑 Это может занять некоторое время...")

            count = 0
            auth_ids = {}
            async for m in ctx.channel.history(limit=None, before=before, after=after):
                count += 1
                if m.author.id not in auth_ids:
                    auth_ids[m.author.id] = 1
                else:
                    auth_ids[m.author.id] += 1
            
            plus_3 = timedelta(hours=3)
            usercount = 0
            desc = ""
            for i, pair in enumerate(sorted(list(auth_ids.items()), key=lambda p: p[1], reverse=True)):
                ID, num = pair
                member = ctx.guild.get_member(ID)
                desc += f"{i + 1}. Тег: {member}\tID: {ID}\tСообщений: {num}\n"
                usercount += 1
            del auth_ids
            
            btext = BytesIO(desc.encode("utf-8"))
            reply = discord.Embed(color=discord.Color.magenta())
            reply.title="📅 Итог подсчёта"
            reply.description=(
                f"**Период:** с `{after + plus_3}` по `{before + plus_3}` (`МСК`)\n\n"
                f"**Всего написано сообщений в указанный период:** `{count}`\n\n"
                f"**Всего пользователей, писавших сообщения:** `{usercount}`"
            )
            reply.set_footer(text="Рассматривались сообщения только в этом канале")
            await ctx.send(embed=reply, file=discord.File(btext, "user_data.txt"))


    @commands.cooldown(1, 1, commands.BucketType.member)
    @commands.command(
        aliases=["choose-from-role", "role-lottery", "cfr"],
        help="выбрать некоторый обладателей роли",
        description="выбирает случайных обладателей указанной роли",
        brief="Число-людей Роль",
        usage="10 Участник" )
    async def choose_from_role(self, ctx, num: int, *, role: discord.Role):
        roleowners = [m for m in ctx.guild.members if role in m.roles]
        shuffle(roleowners)
        roleowners = roleowners[:num]
        desc = ""
        for i, winner in enumerate(roleowners):
            desc += f"`{i + 1}.` {antiformat(winner)} | *`{winner.id}`*\n"
        del roleowners
        reply = discord.Embed(
            title=f"🎲 | Случайно выбраны обладатели роли [{role.name}]",
            description=desc[:2048],
            color=discord.Color.blurple()
        )
        reply.set_thumbnail(url=ctx.guild.icon_url)
        if len(desc) > 2048:
            reply.set_footer(text="Текст мог быть обрезан из-за слишком больших размеров текста")
        del desc
        await ctx.send(embed=reply)


    @commands.cooldown(1, 300, commands.BucketType.member)
    @commands.command(
        aliases=["шар"],
        help="узнать правду",
        description="отвечает на любой Ваш вопрос и почти всегда невпопад.",
        brief="вопрос",
        usage="Мне суждено играть в бравл старс?" )
    async def ball(self, ctx, *, query):
        qwords = {
            "почему": [
                "Потому что каждый раз, когда земля делает один оборот вокруг своей оси, проходит 24 часа.",
                "Потому что если бы это было не так, было бы не интересно.",
                "Хотя бы думай, прежде чем задаёшь такие вопросы.",
                "Потому что у куропаток нет чёткого периода подросткового возраста.",
                "А почему нет?",
                "Потому что кукуруза - это вкусная еда. Потому что кукуруза - это мясо, колбаса.",
                "Меньше знаешь - крепче спишь.",
                "Потому что кукуруза - это вкусная еда. Потому что кукуруза - это мясо, колбаса!",
                f"Причина очень проста - {choice(['Эквенос', 'я', 'Инди'])} гей.",
                "Причина в том, что человечество дико воняет."
            ],
            "как": [
                "Сначала нужно выпрямить спину. Затем аккуратно наклониться, выдохнуть и задуматься о смысле своего существования.",
                "Ты наверное хочешь услышать от меня пошаговый гайд. Что ж, сегодня мне лень растопыриваться и объяснять это, впрочем, как и в любой другой день.",
                "Я бы посоветовал тегнуть оптимиста и задать ему тот же вопрос.",
                "Всё очень просто - подпишись на Влада А4.",
                "Пункт первый - удалить бравл старс. Пункт второй - не допустить повторения первого пункта.",
                "Аккуратно протираешь свой экран, хех хех ммммм... Иногда, бывает просто плохо видно.",
                "Никак.",
                "Внимательно прочитай инструкцию на упаковке.",
                "Тегни уже оптимиста, не тяни кота за хвост."
            ],
            "зачем": [
                "Чтобы кто-нибудь вроде тебя лишний раз прописал эту команду и улучшил статистику сервера.",
                "Лишним это точно не будет.",
                "Учёные пока этого не выяснили.",
                "Я долго размышлял над твоим вопросом - примерно 100 миллисекунд - и пришёл к выводу, что это просто полезно для здоровья.",
                "Затем, что это положительно влияет на магнитосферу Земли (если кто не знал).",
                "Сколько бы ты ни спрашивал, Инквизитор и Сеня будут записывать каждое твоё движение.",
                "Чтобы Байден стал президентом США.",
                "Затем, что это хорошо сказывается на здоровье средне азиатских слонов."
            ],
            "где": [
                "Под столом. И это не обсуждается.",
                "Не так близко, как хотелось бы.",
                "В депрессии. Просто отстаньте...",
                "Есть вещи, которые мне знать не положено.",
                "Я бы хотел ответить что-нибудь в рифму, но есть шанс, что это будет нецензурно.",
                "В навигации.",
                "А ты как думаешь? Конечно в России.",
                "В журнале Ералаш.",
                "В кинотеатрах России.",
                "На острове, где таких вопросов не задают, а гифты приходят сразу после того, как ты их выигрываешь.",
                "С твоей мамашей. Прости пожалуйста.",
                "На Байкале. Кстати, некоторым людям я рекомендую подписаться на Влада А4. Мне стыдно."
            ],
            "сколько": [
                f"Тебе и правда интересно? {randint(1, 10000)}",
                f"Даже по моим меркам это совсем немного - {randint(1, 10000)}",
                f"Боюсь даже предположить, откуда я взял это число - {randint(1, 10000)}",
                f"Если эти циферки доставят хотя бы малейшее удовлетворение, то {randint(1, 10000)}",
                f"Загадка Жака Фреско",
                f"Дай-ка кину кубик. {randint(1, 6)}.",
                f"Ну смотри. Сегодня в моей вселенной выпало {randint(5, 150)} миллиметров осадков, а трафик загружен на {randint(1, 10)}/10. Отсюда делаем вывод, что ответ на твой вопрос - {randint(1,500)}.",
                f"Ооо, тоже любишь приключения? Круто, я их ненавижу. А, чуть не забыл ответить - {randint(1, 1000)}.",
                f"{randint(1, 20000)}. Сначала может показаться, что неоправданно много. Но это заблуждение."
            ],
            "когда": [
                "Не слишком скоро.",
                f"Помнится я как-то раз подтёрся газетой с этой датой - {datetime(randint(1, 3000), randint(1, 12), randint(1, 28))}",
                "Никогда. Неожиданный ответ? Привыкайте.",
                "А какая разница? Все мы рано или поздно уйдём в небытие, все эти мелкие ничего не стоящие события только отвлекают.",
                "где",
                "Завтра.",
                f"Через несколько недель - {randint(2, 10)}",
                f"В {randint(2050, 3050)} году. Может быть даже в это же время.",
                "Вчера. Ладно, шучу. Позавчера.",
                "Когда, скажем, рак на горе свиснет.",
                f"Через {randint(5, 13)} недель, {randint(2, 4)} дня, {randint(5, 20)} часов, {choice([randint(5, 20), randint(25, 30)])} минут и 1 секунду."
            ],
            "кому": [
                "Ну, например, мне.",
                "Очевидно, любому человеку, чьё имя Сергей.",
                "Не знаю. Но кто бы он ни был, я бы не был против познакомиться с ним поближе.",
                "Инвалидам, пассажирам с детьми и беременным женщинам.",
                "Детям, конечно же.",
                f"Работникам {choice(['Макдоналдс', 'Тинькофф', 'Гейм.тв', 'Бургер Кинг', 'KFC', 'Блусткса'])}.",
                f"Надёжным людям. Например {choice(['Квиту', 'Эквеносу', 'Оптимисту', 'Инквизитору', 'Сене', 'Троллю', 'Нду'])}.",
                "Путину?",
                "Китайским олимпийским чемпионам.",
                "Азербайджанским сектантам.",
                "Как бы странно это ни звучало, средне азиатским бурундукам."
            ],
            "кто": [
                f"Это ж как надо отстать от жизни? {choice(['Квит', 'Эквенос', 'Оптимист', 'Тролль', 'Инквизитор', 'Сеня', 'Генерал Панк', 'Вернон'])} конечно же!",
                "Лучше бы ты не спрашивал. Это твой дед.",
                "Не кто, а что. Велосипед.",
                "Карыч или Лосяш, точно не помню. Они оба выглядят подозрительно.",
                choice(['Красный', 'Синий', 'Желтый', 'Зеленый', 'Оранжевый', 'Коричневый', 'Белый', 'Черный', 'Фиолетовый', 'Розовый', 'Голубой']),
                "Соседский рыжий кот. Он скорее всего скрывается прямо сейчас.",
                "Байден, он вроде в выборах победил",
                "Инопланетная цивилизация из созвездия Лиры.",
                "Рабовладелец в древнем Египте.",
                "Главный инженер Гитлера.",
                "Я надеюсь вам достаточно весело, чтобы пережить этот момент. Это тренер сборной России по футболу.",
                "Любимый хомячок Дуэйна Джонсона."
            ]
        }
        yesno = [
            "Очень маловероятно.",
            "Однозначно.",
            "Несмотря на то, что я весьма сильно ударился головой, могу точно сказать, что нет.",
            "Ну конечно!",
            "Я рад, что ты спросил. Нет.",
            "Ещё мой дед говорил, что да.",
            "Дай-ка подумать. Хах... нет.",
            "Ну вообще-то да.",
            "Эмммм... Нет.",
            "Вероятность этого крайне мала.",
            "Да! Да! ДА!!!",
            "О Господи. Нет.",
            "По английски yes. Уагадай как по-русски. Ладно, скажу - да.",
            "Ну, как тебе сказать... Пожалуй нет.",
            "Ахах, топ вопрос - ну конечно!",
            "Вроде нет... Тут же нет подвоха?"
        ]

        ans = None
        query = query.lower()
        words = query.split()
        if "или" in words:
            i = words.index("или")
            if 0 < i < len(words) - 1:
                ans = choice([words[i - 1], words[i + 1]])
                if ans[-1:] in "?!.,;:":
                    ans = ans[:-1]
                ans = ans[0].upper() + f"{ans[1:]}. " + choice(["Выбрать было непросто.", "Очевидно же", "Стыдно не знать.", "Как завещал Жак Фреско.", "Стесняюсь спросить, зачем тебе это знать?"])
        if ans is None:
            for qw in qwords:
                if qw in query:
                    ans = choice(qwords[qw])
                    break
            if ans is None:
                ans = choice(yesno)
        await ctx.send(ans)

    #----------------------------------------------+
    #                   Errors                     |
    #----------------------------------------------+


def setup(client):
    client.add_cog(utils(client))