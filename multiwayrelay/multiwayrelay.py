import pathlib
import discord
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
import re
import itertools
from __main__ import settings

path = 'data/multiwayrelay'


class MultiWayRelay:
    """
    Multiway channel linkage
    """

    __author__ = "mikeshardmind (Sinbad#0001)"
    __version__ = "2.2.1"

    def __init__(self, bot):
        self.bot = bot
        try:
            self.settings = dataIO.load_json(path + '/settings.json')
        except Exception:
            self.settings = {}
        try:
            self.bcasts = dataIO.load_json(path + '/settings-bcasts.json')
        except Exception:
            self.bcasts = {}
        try:
            self.rss = dataIO.load_json(path + '/settings-rss.json')
        except Exception:
            self.rss = {
                'links': {},
                'opts': {}
            }
        self.links = {}
        self.activechans = []
        self.initialized = False

    def save_json(self):
        dataIO.save_json(path + '/settings.json', self.settings)
        dataIO.save_json(path + '/settings-bcasts.json', self.bcasts)
        dataIO.save_json(path + '/settings-rss.json', self.rss)

    @commands.group(name="relay", pass_context=True)
    async def relay(self, ctx):
        """
        relay settings
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.is_owner()
    @relay.command(name="make", pass_context=True)
    async def makelink(self, ctx, name: str, *chanids: str):
        """takes a name (no whitespace) and a list of channel ids"""
        name = name.lower()
        if name in self.settings:
            return await self.bot.say("that name is in use")

        channels = self.bot.get_all_channels()
        channels = [c for c in channels if c.type == discord.ChannelType.text]
        channels = [c.id for c in channels if c.id in chanids]

        if any(i in self.activechans for i in channels):
            await self.bot.say("Warning: One or more of these channels is "
                               "already linked elsewhere")

        channels = unique(channels)

        if len(channels) >= 2:
            self.settings[name] = {'chans': channels}
            self.save_json()
            await self.validate()
            if name in self.links:
                await self.bot.say("Relay formed.")
        else:
            await self.bot.say("I did not get two or more valid channel IDs")

    @checks.is_owner()
    @relay.command(name="addto", pass_context=True)
    async def addtorelay(self, ctx, name: str, *chanids: str):
        """add chans to a relay"""

        name = name.lower()
        if name not in self.settings:
            return await self.bot.say("that relay doesnt exist")

        chanids = list(chanids) + self.settings[name]['chans']
        channels = self.bot.get_all_channels()
        channels = [c for c in channels if c.type == discord.ChannelType.text]
        channels = [c.id for c in channels if c.id in chanids]

        if any(i in self.activechans for i in channels):
            await self.bot.say("Warning: One or more of these channels is "
                               "already linked elsewhere")

        channels = unique(channels)

        self.settings[name] = {'chans': channels}
        self.save_json()
        await self.validate()
        await self.bot.say("Relay updated.")

    @checks.is_owner()
    @relay.command(name="remfrom", pass_context=True)
    async def remfromrelay(self, ctx, name: str, *chanids: str):
        """remove chans from a relay"""

        name = name.lower()
        if name in self.settings:
            return await self.bot.say("that relay doesnt exist")

        self.settings[name]['chans']
        for cid in chanids:
            if cid in self.settings[name]['chans']:
                self.settings[name]['chans'].remove(cid)

        self.save_json()
        await self.validate()
        await self.bot.say("Relay updated.")

    @checks.is_owner()
    @relay.command(name="remove", pass_context=True)
    async def unlink(self, ctx, name: str):
        """removes a relay by name"""
        name = name.lower()
        if name in self.links:
            chans = self.links[name]
            self.activechans = [cid for cid in self.activechans
                                if cid not in [c.id for c in chans]]
            self.links.pop(name, None)
            self.settings.pop(name, None)
            self.save_json()
            await self.bot.say("Relay removed")
        else:
            await self.bot.say("No such relay")

    @checks.is_owner()
    @relay.command(name="addrss", pass_context=True, hidden=True)
    async def add_rss_support(self, ctx, rss_channel: discord.Channel):
        """
        takes an rss listening channel
        """
        existing = self.rss.get('links', [])
        if isinstance(existing, dict):
            # This is what I get for modifying storage
            self.rss['links'] = list(existing.keys()) + [rss_channel.id]
        else:
            self.rss['links'] = existing + [rss_channel.id]

        self.save_json()
        await self.bot.say("RSS listener added.")

    @checks.is_owner()
    @relay.command(name="broadfromannounce", pass_context=True, hidden=True)
    async def mfromannounce(self, ctx, source_chan: discord.Channel):
        """
        Plugs into my announcer cog to grab subscribed channels
        and make a broadcast channel for them
        """
        announcer = self.bot.get_cog("Announcer")
        if announcer is None:
            return await self.bot.send_cmd_help(ctx)
        self.bcasts = {
            source_chan.id: unique(
                [v['channel'] for k, v in announcer.settings.items()]
            )
        }
        self.save_json()
        await self.bot.say('Broadcast configured.')

    @checks.serverowner_or_permissions(manage_server=True)
    @relay.command(
        name="getbroadcasts", pass_context=True, no_pm=True, hidden=True)
    async def get_broadcasts(self, ctx, channel: discord.Channel):
        """
        joins one of your server's channels to the list of broadcast recipients
        """
        if len(self.bcasts) == 0:
            return await self.bot.say("No broadcasts available to get")
        if channel.server != ctx.message.server \
                and ctx.message.author.id not in \
                ctx.bot.settings.co_owners + [settings.owner]:
            return await self.bot.say("Nice try.")
        if any(v == channel.id for v in self.bcasts.values()):
            return await self.bot.say("Already signed up.")
        self.bcasts = {
            k: unique(v + [channel.id])
            for k, v in self.bcasts.items()
        }
        self.save_json()
        await self.bot.say("Signed up for broadcasts here.")

    @checks.serverowner_or_permissions(manage_server=True)
    @relay.command(name="stopbroadcasts", pass_context=True, hidden=True)
    async def stop_broadcasts(self, ctx, channel: discord.Channel):
        """
        leaves broadcasts on a channel
        """
        if len(self.bcasts) == 0:
            return await self.bot.say("No broadcasts available to leave")
        if channel.server != ctx.message.server \
                and ctx.message.author.id not in \
                ctx.bot.settings.co_owners + [settings.owner]:
            return await self.bot.say("Nice try.")
        if not any(v == channel.id for v in self.bcasts.values()):
            return await self.bot.say("Not signed up for any broadcasts.")

        self.bcasts = {
            k: [c_id for c_id in v if c_id != channel.id]
            for k, v in self.bcasts.items()
        }
        self.save_json()
        await self.bot.say("No more broadcasts here.")

    @checks.is_owner()
    @relay.command(name="makebroadcast", pass_context=True, hidden=True)
    async def mbroadcast(self, ctx, broadcast_source: discord.Channel):
        """
        takes a source channel
        """
        if broadcast_source.id in self.bcasts.keys():
            return await self.bot.say(
                "Channel already set as broadcast source"
            )

        self.bcasts = {broadcast_source.id: []}
        self.save_json()
        await self.bot.say('Broadcast source set.')

    @checks.is_owner()
    @relay.command(name="list", pass_context=True)
    async def list_links(self, ctx):
        """lists the channel links by name"""

        links = list(self.settings.keys())
        await self.bot.say("Active relay names:\n {}".format(links))

    async def validate(self):
        channels = self.bot.get_all_channels()
        channels = [c for c in channels if c.type == discord.ChannelType.text]

        for name in self.settings:
            chan_ids = list(*self.settings[name].values())
            chans = [c for c in channels if c.id in chan_ids]
            self.links[name] = chans
            self.activechans += chan_ids

    async def do_stuff_on_message(self, message):
        """Do stuff based on settings"""
        if not self.initialized:
            await self.validate()
            self.initialized = True
        channel = message.channel
        destinations = set()

        if message.author != self.bot.user:
            for link in self.links:
                if channel in self.links[link]:
                    destinations.update(
                        c for c in self.links[link]
                        if c != channel
                    )

            destinations.update(
                [c for c in self.bot.get_all_channels()
                 if c.id in self.bcasts.values()
                 and c.type == discord.ChannelType.text]
            )

            for destination in destinations:
                await self.sender(destination, message)

        else:  # RSS Relay Stuff
            if channel.id not in self.rss.get('links', []):
                return
            if not message.content.startswith("\u200b"):
                return
            destinations.update(
                [c for c in self.bot.get_all_channels()
                 if c.id in self.bcasts.values()
                 and c.type == discord.ChannelType.text]
            )
            for destination in destinations:
                await self.rss_sender(destination, message)

    async def rss_sender(self, where, message=None):
        if message:
            msg = "\u200C{}".format(
                self.role_mention_cleanup(message)[1:]
            )
            try:
                await self.bot.send_message(where, msg)
            except Exception:
                pass

    async def sender(self, where, message=None):
        """sends the thing"""

        if message:
            em = self.qform(message)
            try:
                await self.bot.send_message(where, embed=em)
            except Exception:
                pass

    def role_mention_cleanup(self, message):

        if message.server is None:
            return message.content

        transformations = {
            re.escape('<@&{0.id}>'.format(role)): '@' + role.name
            for role in message.role_mentions
        }

        def repl(obj):
            return transformations.get(re.escape(obj.group(0)), '')

        pattern = re.compile('|'.join(transformations.keys()))
        result = pattern.sub(repl, message.content)

        return result

    def qform(self, message):
        channel = message.channel
        server = channel.server
        content = self.role_mention_cleanup(message)
        author = message.author
        sname = server.name
        cname = channel.name
        avatar = author.avatar_url if author.avatar \
            else author.default_avatar_url
        footer = 'Said in {} #{}'.format(sname, cname)
        em = discord.Embed(description=content, color=author.color,
                           timestamp=message.timestamp)
        em.set_author(name='{}'.format(author.name), icon_url=avatar)
        em.set_footer(text=footer, icon_url=server.icon_url)
        if message.attachments:
            a = message.attachments[0]
            fname = a['filename']
            url = a['url']
            if fname.split('.')[-1] in ['png', 'jpg', 'gif', 'jpeg']:
                em.set_image(url=url)
            else:
                em.add_field(name='Message has an attachment',
                             value='[{}]({})'.format(fname, url),
                             inline=True)
        return em


def unique(a):
    indices = sorted(range(len(a)), key=a.__getitem__)
    indices = set(next(it) for k, it in
                  itertools.groupby(indices, key=a.__getitem__))
    return [x for i, x in enumerate(a) if i in indices]


def setup(bot):
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)
    n = MultiWayRelay(bot)
    bot.add_listener(n.do_stuff_on_message, "on_message")
    bot.add_cog(n)
