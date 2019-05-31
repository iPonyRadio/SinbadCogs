import asyncio

import discord
from redbot.core import commands, context
from redbot.core.config import Config


class Scheduler(commands.Cog):
    """
    A more sane version of the scheduler
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=78631113035100160_2, force_registration=True
        )
        self.config.register_global(extra_on_message=["Alias", "CustomCom"])
        self.config.register_user(timezone=None)
        self.config.init_custom("REMINDERS", 1)
        self.config.init_custom("SCHEDULED_COMMANDS", 1)
        self.config.init_custom("EXTERNALLY_SCHEDULED", 2)
        self.config.register_custom(
            "REMINDERS",
            who=None,
            message=None,
            channel=None,
            start=None,
            repeat=None,
            snooze_until=None,
            reminder_content=None,
        )
        self.config.register_custom(
            "SCHEDULED_COMMANDS",
            author=None,
            message=None,
            channel=None,
            start=None,
            repeat=None,
            snooze_until=None,
            command=None,
        )
        self.config.register_custom(
            "EXTERNALLY_SCHEDULED",
            author=None,
            message=None,
            channel=None,
            start=None,
            repeat=None,
            snooze_until=None,
            command=None,
            cog=None,
        )

        self._main_loop_task = asyncio.create_task(self.main_loop())
        self._extra_tasks = {}

    def cog_unload(self):
        self._main_loop_task.cancel()
        for task in list(self.extra_tasks.values()):
            task.cancel()

    async def main_loop(self):
        return
        while True:
            pass

    async def do_scheduled(self, scheduled):
        pass

    async def do_reminder(self, reminder):
        pass

