import discord
import re

class LinkJoinKiller:
    """
    Auto-ban users joining with invites in name.
    """

    __author__ = "mikeshardmind(Sinbad#0001)"
    __version__ = '0.0.1a'

    def __init__(self, bot):
        self.regex = re.compile(
            r"<?(https?:\/\/)?(www\.)?(discord\.gg|discordapp\.com\/invite)\b([-a-zA-Z0-9/]*)>?"
        )
        self.bot = bot

    async def on_member_join(self, member):
        if not member.server.me.server_permissions.ban_members:
            return
        if self.regex.search(str(member)) is not None:
            await self.bot.http.ban(member.id, server.id, 0)


def setup(bot):
    bot.add_cog(LinkJoinKiller(bot))
