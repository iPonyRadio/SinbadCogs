from redbot.core import commands, errors
from redbot import version_info, VersionInfo
from .core import Scheduler


def setup(bot):
    if version_info < VersionInfo.from_str("3.1.2"):
        raise errors.CogLoadError("You need at least version `3.1.2`")
    if bot.user.id != 275047522026913793:
        raise errors.CogLoadError("You really shouldn't try and play with undocumented things yet.")
    
    bot.add_cog(Scheduler(bot))