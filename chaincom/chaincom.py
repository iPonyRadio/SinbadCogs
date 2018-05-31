import discord
from discord.ext import commands
import time
from random import randint


class ChainCom:
    """
    Chain Commands together.
    """

    __author__ = "mikeshardmind (Sinbad#0413)"
    __version__ = "0.0.1a"

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, name="chain")
    async def dpyinternalsabuse(self, ctx, *, coms):
        """
        takes a set of commands with parameters, seperated by

        |

        (yes, that's a pipe)
        No real internal checking that you didnt fuck up, and this also does
        not wait for command completion before doing the next one.
        """
        commands = [c.strip() for c in coms.split('|')]
        for com in commands:

            data = \
                {'timestamp': time.strftime("%Y-%m-%dT%H:%M:%S%z",
                                            time.gmtime()),
                 'content': ctx.prefix + com,
                 'channel': ctx.message.channel,
                 'channel_id': ctx.message.channel.id,
                 'author': {'id': ctx.message.author.id},
                 'nonce': randint(1, (2**32) - 1),
                 'id': randint(10**(17), (10**18) - 1),
                 'reactions': []
                 }
            message = discord.Message(**data)
            self.bot.dispatch('message', message)


def setup(bot):
    bot.add_cog(ChainCom(bot))
