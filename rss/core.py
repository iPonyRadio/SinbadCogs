import asyncio
import string
from typing import Optional, List, cast, no_type_check
from datetime import datetime

import aiohttp
import logging

import feedparser
import discord

from redbot.core import commands, checks
from redbot.core.config import Config
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import pagify

from .cleanup import html_to_text
from .converters import tristate  # typing: ignore


_ = Translator("RSS", __file__)

log = logging.getLogger("red.sinbadcogs.rss")

DONT_HTML_SCRUB = ["link", "source", "updated", "updated_parsed"]

USABLE_FIELDS = [
    "author",
    "author_detail",
    "description",
    "comments",
    "content",
    "contributors",
    "created",
    "updated",
    "updated_parsed",
    "link",
    "name",
    "published",
    "published_parsed",
    "publisher",
    "publisher_detail",
    "source",
    "summary",
    "summary_detail",
    "tags",
    "title",
    "title_detail",
]


@cog_i18n(_)
class RSS(commands.Cog):
    """
    An RSS cog.
    
    Sponsored by aikaterna, the most helpful of cats.
    """

    __author__ = "mikeshardmind(Sinbad)"
    __version__ = "1.0.23"
    __flavor_text__ = "Slow responses wont kill the loop now."

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=78631113035100160, force_registration=True
        )
        self.config.register_channel(feeds={})
        self.session = aiohttp.ClientSession()
        self.bg_loop_task = self.bot.loop.create_task(self.bg_loop())

    def cog_unload(self):
        self.bg_loop_task.cancel()
        self.session.detach()

    __del__ = cog_unload

    def clear_feed(self, channel, feedname):
        """
        This is abuse.
        """
        return self.config.channel(channel).clear_raw("feeds", feedname)

    async def should_embed(self, guild: discord.Guild) -> bool:
        ret: bool = await self.bot.db.guild(guild).embeds()
        if ret is None:
            ret = await self.bot.db.embeds()
        return ret

    async def fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        timeout = aiohttp.client.ClientTimeout(total=15)
        try:
            async with self.session.get(url, timeout=timeout) as response:
                data = await response.read()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None
        except Exception as exc:
            log.exception(
                f"Unexpected exception type {type(exc)} encountered for feed url: {url}",
                exc_info=True,
            )
            return None

        ret = feedparser.parse(data)
        if ret.bozo:
            log.info(f"Feed url: {url} is invalid.")
            return None
        return ret

    @staticmethod
    def process_entry_time(x):
        if "published_parsed" in x:
            return tuple(x.get("published_parsed"))[:5]
        if "updated_parsed" in x:
            return tuple(x.get("updated_parsed"))[:5]
        return (0,)

    async def format_and_send(
        self,
        *,
        destination: discord.abc.Messageable,
        response: feedparser.FeedParserDict,
        feed_settings: dict,
        embed_default: bool,
        force: bool = False,
    ) -> Optional[List[int]]:
        """
        Formats and sends, 
        returns the integer timestamp of latest entry in the feed which was sent
        """

        use_embed = feed_settings.get("embed_override", None)
        if use_embed is None:
            use_embed = embed_default

        if force:
            try:
                to_send = [response.entries[0]]
            except IndexError:
                return None
        else:
            last = feed_settings.get("last", None)
            last = tuple((last or (0,))[:5])

            to_send = sorted(
                [e for e in response.entries if self.process_entry_time(e) > last],
                key=self.process_entry_time,
            )

        last_sent = None
        for entry in to_send:
            color = destination.guild.me.color
            kwargs = self.format_post(
                entry, use_embed, color, feed_settings.get("template", None)
            )
            try:
                await self.bot.send_filtered(destination, **kwargs)
            except discord.HTTPException:
                continue
            last_sent = list(self.process_entry_time(entry))

        return last_sent

    def format_post(self, entry, embed: bool, color, template=None) -> dict:

        if template is None:
            if embed:
                _template = "[$title]($link)"
            else:
                _template = "$title: <$link>"
        else:
            _template = template

        template = string.Template(_template)

        data = {k: getattr(entry, k, None) for k in USABLE_FIELDS}

        def maybe_clean(key, val):
            if isinstance(val, str) and key not in DONT_HTML_SCRUB:
                return html_to_text(val)
            return val

        escaped_usable_fields = {k: maybe_clean(k, v) for k, v in data.items() if v}

        content = template.safe_substitute(**escaped_usable_fields)

        if embed:
            if len(content) > 1980:
                content = content[:1900] + _("... (Feed data too long)")
            timestamp = datetime(*self.process_entry_time(entry))
            embed_data = discord.Embed(
                description=content, color=color, timestamp=timestamp
            )
            embed_data.set_footer(text=_("Published "))
            return {"content": None, "embed": embed_data}
        else:
            if len(content) > 1950:
                content = content[:1950] + _("... (Feed data too long)")
            return {"content": content, "embed": None}

    async def bg_loop(self):
        await self.bot.wait_until_ready()
        while self.bot.get_cog("RSS") == self:
            feeds_fetched = {}
            default_embed_settings = {}

            channel_data = await self.config.all_channels()
            for channel_id, data in channel_data.items():

                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue
                if channel.guild not in default_embed_settings:
                    should_embed = await self.should_embed(channel.guild)
                    default_embed_settings[channel.guild] = should_embed
                else:
                    should_embed = default_embed_settings[channel.guild]

                for feed_name, feed in data["feeds"].items():
                    url = feed.get("url", None)
                    if not url:
                        continue
                    if url in feeds_fetched:
                        response = feeds_fetched[url]
                    else:
                        response = await self.fetch_feed(url)
                        feeds_fetched[url] = response

                    if response:
                        try:
                            last = await self.format_and_send(
                                destination=channel,
                                response=response,
                                feed_settings=feed,
                                embed_default=should_embed,
                            )
                        except Exception:
                            pass
                        else:
                            if last:
                                await self.config.channel(channel).feeds.set_raw(
                                    feed_name, "last", value=last
                                )
            await asyncio.sleep(300)  # TODO: configureable

    # commands go here

    @checks.mod_or_permissions(manage_channels=True)
    @commands.group()
    async def rss(self, ctx: commands.Context):
        """
        Configuration for rss
        """
        pass

    @rss.command(name="force")
    async def rss_force(self, ctx, feed, channel: Optional[discord.TextChannel] = None):
        """
        Forces the latest update for a feed to post.
        """

        channel = channel or ctx.channel
        feeds = await self.config.channel(channel).feeds()
        url = None
        if feed in feeds:
            url = feeds[feed].get("url", None)

        if url is None:
            return await ctx.send(_("No such feed."))

        response = await self.fetch_feed(url)

        should_embed = await self.should_embed(ctx.guild)

        try:
            await self.format_and_send(
                destination=channel,
                response=response,
                feed_settings=feeds[feed],
                embed_default=should_embed,
                force=True,
            )
        except Exception:
            await ctx.send(_("There was an error with that."))
        else:
            await ctx.tick()

    @commands.cooldown(3, 60, type=commands.BucketType.user)
    @rss.command()
    async def addfeed(
        self,
        ctx: commands.Context,
        name: str,
        url: str,
        channel: Optional[discord.TextChannel] = None,
    ):
        """
        Adds a feed to the current, or a provided channel
        """

        channel = channel or ctx.channel

        async with self.config.channel(channel).feeds() as feeds:
            if name in feeds:
                return await ctx.send(_("That name is already in use."))

            response = await self.fetch_feed(url)

            if response is None:
                return await ctx.send(
                    _("That didn't seem to be a valid rss feed. (Syntax: {}{})").format(
                        ctx.prefix, ctx.command.signature
                    )
                )

            else:
                feeds.update(
                    {
                        name: {
                            "url": url,
                            "template": None,
                            "embed_override": None,
                            "last": list(ctx.message.created_at.timetuple()[:6]),
                        }
                    }
                )

        await ctx.tick()

    @rss.command(name="list")
    async def list_feeds(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ):
        """
        Lists the current feeds for the current channel, or a provided one.
        """

        channel = channel or ctx.channel

        data = await self.config.channel(channel).feeds()

        if await ctx.embed_requested():
            output = "\n".join(
                [
                    "{name}: {url}".format(name=k, url=v.get("url", "broken feed"))
                    for k, v in data.items()
                ]
            )
            for page in pagify(output):
                await ctx.send(
                    embed=discord.Embed(
                        description=page, color=(await ctx.embed_color())
                    )
                )
        else:
            output = "\n".join(
                [
                    "{name}: <{url}>".format(name=k, url=v.get("url", "broken feed"))
                    for k, v in data.items()
                ]
            )
            for page in pagify(output):
                await ctx.send(page)

    @rss.command(name="remove")
    async def remove_feed(
        self, ctx, name: str, channel: Optional[discord.TextChannel] = None
    ):
        """
        removes a feed from the current channel, or from a provided channel

        If the feed is currently being fetched, there may still be a final update
        after this.
        """
        channel = channel or ctx.channel
        await self.clear_feed(channel, name)
        await ctx.tick()

    @rss.command(name="embed")
    @no_type_check
    async def set_embed(
        self,
        ctx,
        feed: str,
        setting: tristate,
        channel: Optional[discord.TextChannel] = None,
    ):
        """
        Sets if a specific feed should 
            use an embed, 
            not use an embed, 
            or (default) use the bot setting to determine embed usage.

        Valid Settings for this are:
            True
            False
            Default
        """

        channel = channel or ctx.channel
        await self.config.channel(channel).set_raw(
            "feeds", feed, "embed_override", value=setting
        )
        await ctx.tick()

    @rss.command(name="template")
    async def set_template(
        self,
        ctx,
        feed,
        channel: Optional[discord.TextChannel] = None,
        *,
        template: str = None,
    ):
        """
        Sets formatting for the specified feed in this, or a provided channel

        The following have special meaning based on their content in the RSS feed data.
        Any not used will remain.

        $author
        $author_detail
        $description
        $comments
        $content
        $contributors
        $updated
        $updated_parsed
        $link
        $name
        $published
        $published_parsed
        $publisher
        $publisher_detail
        $source
        $summary
        $summary_detail
        $tags
        $title
        $title_detail

        """

        if not template:
            return await ctx.send_help()

        channel = channel or ctx.channel
        template = template.replace("\\t", "\t")
        template = template.replace("\\n", "\n")
        await self.config.channel(channel).set_raw(
            "feeds", feed, "template", value=template
        )
        await ctx.tick()

    @rss.command(name="resettemplate")
    async def reset_template(
        self, ctx, feed, channel: Optional[discord.TextChannel] = None
    ):
        """
        Resets the template in use for a specific feed in this, or a provided channel
        """
        channel = channel or ctx.channel
        await self.config.channel(channel).clear_raw("feeds", feed, "template")
        await ctx.tick()
