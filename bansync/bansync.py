import asyncio
import discord
from discord.ext import commands
from .utils import checks
from cogs.utils.chat_formatting import box, pagify

path = "data/bansync"


class BanSync:
    """
    Syncs bans between servers
    """

    __version__ = "1.3.1"
    __author__ = "mikeshardmind (Sinbad#0001)"

    def __init__(self, bot):
        self.bot = bot
        self.modlog = self.bot.get_cog("Mod")

    @checks.is_owner()
    @commands.command(hidden=True, pass_context=True)
    async def bulkban(self, ctx, *users):
        """
        Use at own risk, attempts to globalban a large user list
        """

        com =  self.bot.get_command('globalban')
        for user in users:
            try:
                await com.callback(com.instance, ctx, user=user)
            except:
                pass


    @checks.is_owner()
    @commands.command(name="globalban", pass_context=True)
    async def globalban(self, ctx, *, user):
        """
        ban someone in each server the bot can ban
        """

        try:
            _u = commands.converter.MemberConverter().convert(ctx, user)
        except commands.BadArgument:
            try:
                _id = str(int(user))  # This is a messy thing, sorry
            except ValueError:
                raise commands.BadArgument('Invalid user')
        else:
            _id = _u.id

        for server in self.bot.servers:
            if not server.me.server_permissions.ban_members:
                continue
            member = server.get_member(_id)
            if member is not None:
                try:
                    await self.bot.ban(member, delete_message_days=0)
                except discord.Forbidden:
                    return await self.bot.whisper("I can't do that")
                else:
                    if self.modlog:
                        await self.modlog.new_case(server, user=member, action="BAN")
            else:
                try:
                    await self.bot.http.ban(user.id, server.id, 0)
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    return await self.bot.whisper("I can't do that")
                else:
                    if self.modlog:
                        await self.modlog.new_case(server, action="HACKBAN", user=user)

    @checks.is_owner()
    @commands.command(name="bansync", pass_context=True)
    async def bansync(self, ctx, auto: bool = False):
        """
        syncs bans across servers
        """
        servers = []
        if not auto:
            while True:
                s = await self.discover_server(ctx.message.author)
                if s is -1:
                    break
                elif s is None:
                    continue
                else:
                    servers.append(s)
        elif auto is True:
            servers = [
                s for s in self.bot.servers if s.me.server_permissions.ban_members
            ]

        if len(servers) < 2:
            return await self.bot.whisper("I need at least 2 servers to sync")

        bans = {}

        for server in servers:
            try:
                server_bans = await self.bot.get_bans(server)
            except discord.Forbidden:
                return await self.bot.whisper("I can't do that")
            else:
                bans[server.id] = server_bans

        for server in servers:
            to_ban = []
            for _k, v in bans.items():
                to_ban.extend([m for m in v if m not in bans[server.id]])
            for user in to_ban:
                member = server.get_member(user.id)
                if member is not None:
                    if member.top_role >= server.me.top_role:
                        await self.bot.whisper(
                            (
                                "{0.mention} from {0.server.name} "
                                "has a higher top role than me, skipping."
                            ).format(member)
                        )
                        continue
                    try:
                        await self.bot.ban(member, delete_message_days=0)
                    except discord.Forbidden:
                        await self.bot.whisper(
                            (
                                "I couldn't ban {0.mention} from {0.server.name}"
                                "This appears to be due to hierarchy, "
                                "so I'll continue with others."
                            ).format(member)
                        )
                    else:
                        if self.modlog:
                            await self.modlog.new_case(
                                server, user=member, action="BAN", reason="ban sync"
                            )
                    await asyncio.sleep(1)
                else:
                    try:
                        await self.bot.http.ban(user.id, server.id, 0)
                    except discord.NotFound:
                        pass
                    except discord.Forbidden:
                        await self.bot.whisper(
                            (
                                "I can't hack ban user with id {id} from {s.name}, "
                                "this does not appear to be intermittent, "
                                "skipping attempting bans on the rest of this server."
                            ).format(id=user.id, s=server)
                        )
                        break
                    else:
                        if self.modlog:
                            await self.modlog.new_case(
                                server, action="HACKBAN", user=user, reason="ban sync"
                            )

        await self.bot.whisper("bans synced")

    async def discover_server(self, author: discord.User):
        output = ""
        servers = sorted(self.bot.servers, key=lambda s: s.name)
        for i, server in enumerate(servers, 1):
            output += "{}: {}\n".format(i, server.name)
        output += "Select a server to add to the sync list by number, " 'or enter "-1" to stop adding servers'
        for page in pagify(output, delims=["\n"]):
            dm = await self.bot.send_message(author, box(page))

        message = await self.bot.wait_for_message(
            channel=dm.channel, author=author, timeout=15
        )
        if message is not None:
            try:
                message = int(message.content.strip())
                if message == -1:
                    return -1
                else:
                    server = servers[message - 1]
            except (ValueError, IndexError):
                await self.bot.send_message(author, "That wasn't a valid choice")
                return None
            else:
                return server
        else:
            await self.bot.say("You took too long, try again later")
            return None


def setup(bot):
    n = BanSync(bot)
    bot.add_cog(n)
