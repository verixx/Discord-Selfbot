import aiohttp
import datetime
import discord
import json

from discord.ext import commands
from lxml import etree
from urllib.parse import parse_qs
from .utils.helper import edit, permEmbed


class Google:

    def __init__(self, bot):
        self.bot = bot

    def parse_google_card(self, node):
        if node is None:
            return None

        e = discord.Embed(colour=discord.Color.blue())

        # check if it's a calculator card:
        calculator = node.find(".//table/tr/td/span[@class='nobr']/h2[@class='r']")
        if calculator is not None:
            e.title = 'Calculator'
            e.description = ''.join(calculator.itertext())
            return e

        parent = node.getparent()

        # check for unit conversion card
        unit = parent.find(".//ol//div[@class='_Tsb']")
        if unit is not None:
            e.title = 'Unit Conversion'
            e.description = ''.join(''.join(n.itertext()) for n in unit)
            return e

        # check for currency conversion card
        currency = parent.find(".//ol/table[@class='std _tLi']/tr/td/h2")
        if currency is not None:
            e.title = 'Currency Conversion'
            e.description = ''.join(currency.itertext())
            return e

        # check for release date card
        release = parent.find(".//div[@id='_vBb']")
        if release is not None:
            try:
                e.description = ''.join(release[0].itertext()).strip()
                e.title = ''.join(release[1].itertext()).strip()
                return e
            except:
                return None

        # check for definition card
        words = parent.find(".//ol/div[@class='g']/div/h3[@class='r']/div")
        if words is not None:
            try:
                definition_info = words.getparent().getparent()[1]
            except:
                pass
            else:
                try:
                    e.title = words[0].text
                    e.description = words[1].text
                except:
                    return None
                for row in definition_info:
                    if len(row.attrib) != 0:
                        break
                    try:
                        data = row[0]
                        lexical_category = data[0].text
                        body = []
                        for index, definition in enumerate(data[1], 1):
                            body.append('%s. %s' % (index, definition.text))
                        e.add_field(name=lexical_category, value='\n'.join(body), inline=False)
                    except:
                        continue
                return e

        # check for translate card
        words = parent.find(".//ol/div[@class='g']/div/table/tr/td/h3[@class='r']")
        if words is not None:
            e.title = 'Google Translate'
            e.add_field(name='Input', value=words[0].text,  inline=True)
            e.add_field(name='Out', value=words[1].text,  inline=True)
            return e

        # check for "time in" card
        time_in = parent.find(".//ol//div[@class='_Tsb _HOb _Qeb']")
        if time_in is not None:
            try:
                time_place = ''.join(time_in.find("span[@class='_HOb _Qeb']").itertext()).strip()
                the_time = ''.join(time_in.find("div[@class='_rkc _Peb']").itertext()).strip()
                the_date = ''.join(time_in.find("div[@class='_HOb _Qeb']").itertext()).strip()
            except:
                return None
            else:
                e.title = time_place
                e.description = '%s\n%s' % (the_time, the_date)
                return e

        weather = parent.find(".//ol//div[@class='e']")
        if weather is None:
            return None

        location = weather.find('h3')
        if location is None:
            return None

        e.title = ''.join(location.itertext())

        table = weather.find('table')
        if table is None:
            return None

        try:
            tr = table[0]
            img = tr[0].find('img')
            category = img.get('alt')
            image = 'https:' + img.get('src')
            temperature = tr[1].xpath("./span[@class='wob_t']//text()")[0]
        except:
            return None
        else:
            e.set_thumbnail(url=image)
            e.description = '*%s*' % category
            e.add_field(name='Temperature', value=temperature)

        try:
            wind = ''.join(table[3].itertext()).replace('Wind: ', '')
        except:
            return None
        else:
            e.add_field(name='Wind', value=wind)

        try:
            humidity = ''.join(table[4][0].itertext()).replace('Humidity: ', '')
        except:
            return None
        else:
            e.add_field(name='Humidity', value=humidity)

        return e

    async def get_google_entries(self, query):
        params = {
            'q': query,
            'hl': 'en'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64)'
        }
        entries = []
        card = None
        async with aiohttp.ClientSession() as cs:
            async with cs.get('https://www.google.com/search', params=params, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError('Google somehow failed to respond.')

                root = etree.fromstring(await resp.text(), etree.HTMLParser())
                card_node = root.find(".//div[@id='topstuff']")
                card = self.parse_google_card(card_node)
                search_nodes = root.findall(".//div[@class='g']")
                for node in search_nodes:
                    url_node = node.find('.//h3/a')
                    if url_node is None:
                        continue
                    url = url_node.attrib['href']
                    if not url.startswith('/url?'):
                        continue
                    url = parse_qs(url[5:])['q'][0]
                    entries.append(url)
        return card, entries

    # Google Command
    @commands.command(aliases=['google', 'G', 'Google'])
    async def g(self, ctx, *, query):
        """Google for whatever you like."""
        try:
            card, entries = await self.get_google_entries(query)
        except RuntimeError as e:
            await edit(ctx, content=str(e), ttl=3)
        else:
            if card:
                value = '\n'.join(entries[:3])
                if value:
                    card.add_field(name='Search Results', value=value, inline=False)
                return await edit(ctx, embed=card)
            if len(entries) == 0:
                return await edit(ctx, content='No results found... sorry.', ttl=3)
            next_two = entries[1:3]
            before = entries[0]
            before = before[:-1] + '%29' if before[-1] == ')' else before

            e = discord.Embed(colour=discord.Color.blue(), timestamp=datetime.datetime.now())
            e.set_author(name="Google Search", url="https://www.google.com/search?q=" + query.replace(" ", "+"), icon_url="https://cdn.discordapp.com/attachments/278603491520544768/300645219626647564/Google-logo-2015-G-icon.png")
            if next_two:
                formatted = '\n'.join(map(lambda x: '<%s>' % x, next_two))
                e.add_field(name="Search Result", value=before)
                e.add_field(name="More", value=formatted, inline=False)
            else:
                e.add_field(name="Search Result", value=before)
            await edit(ctx, embed=e)

    # Google Image Search (100 per day)
    @commands.command(aliases=["I", "image", "Image"])
    async def i(self, ctx, *, query):
        """Search for images on google."""
        async with aiohttp.ClientSession() as cs:
            async with cs.get("https://www.googleapis.com/customsearch/v1?q=" + query.replace(' ', '+') + "&start=" + '1' + "&key=" + self.bot.google_api_key + "&cx=" + self.bot.custom_search_engine + "&searchType=image") as resp:
                if resp.status != 200:
                    await edit(ctx, content='Google somehow failed to respond.', ttl=3)
                result = json.loads(await resp.text())
                em = discord.Embed(colour=discord.Color.blue())
                if permEmbed(ctx.message):
                    link = result['items'][0]['link']
                    if ".gif?" in link:
                        link = result['items'][0]['link'].split(".gif?")[0] + ".gif"
                    await edit(ctx, content=None, embed=em.set_image(url=link))
                else:
                    await edit(ctx, content=result['items'][0]['link'])


def setup(bot):
    bot.add_cog(Google(bot))
