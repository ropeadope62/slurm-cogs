import discord
import asyncio
from redbot.core import commands, Config, bank
from discord import Interaction
from datetime import datetime, timedelta
from .ui_elements import SelectFightingStyleView, StatIncreaseView
from .fighting_game import FightingGame
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageTransform
from .fighting_constants import INJURY_TREATMENT_COST, XP_REQUIREMENTS, STRIKES
from .bullshido_ai import generate_hype, generate_hype_challenge
import logging
import os


class MemoryLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_records = []

    def emit(self, record):
        self.log_records.append(self.format(record))

    def get_logs(self):
        return self.log_records

    def clear_logs(self):
        self.log_records = []


class Bullshido(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=123123451514345671215451351235890, force_registration=True
        )
        default_user = {
            "fighting_style": None,
            "wins": {"UD": 0, "SD": 0, "TKO": 0, "KO": 0},
            "losses": {"UD": 0, "SD": 0, "TKO": 0, "KO": 0},
            "draws": 0,
            "xp": 0,
            "level": 1,
            "level_points_to_distribute": 0,
            "stamina_bonus": 0,
            "health_bonus": 0,
            "damage_bonus": 0,
            "training_level": 1,
            "nutrition_level": 1,
            "morale": 100,
            "intimidation_level": 0,
            "stamina_level": 100,
            "health_points": 100,
            "prize_money_won": 0,
            "prize_money_lost": 0,
            "last_interaction": None,
            "last_command_used": None,
            "last_train": None,
            "last_diet": None,
            "fight_history": [],
            "permanent_injuries": [],
            "taunts": [],
        }

        default_guild = {
            "rounds": 3,
            "max_strikes_per_round": 5,
            "training_weight": 0.5,
            "diet_weight": 0.3,
            "damage_bonus_weight": 0.5,
            "base_health": 100,
            "action_cost": 10,
            "base_miss_probability": 0.15,
            "base_stamina_cost": 10,
            "critical_chance": 0.1,
            "permanent_injury_chance": 0.5,
            "socialized_medicine": False,
            "socialized_medicine_payer_id": None,
        }

        self.config.register_user(**default_user)
        self.config.register_guild(**default_guild)
        self.setup_logging()
        self.bg_task = self.bot.loop.create_task(self.check_inactivity())
        self.logger.info("Bullshido cog loaded.")

    def setup_logging(self):
        self.logger = logging.getLogger("red.bullshido")
        self.logger.setLevel(logging.DEBUG)

        if not any(
            isinstance(handler, MemoryLogHandler) for handler in self.logger.handlers
        ):
            self.memory_handler = MemoryLogHandler()
            self.logger.addHandler(self.memory_handler)

        log_dir = os.path.expanduser("~/ScrapGPT/ScrapGPT/logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, "bullshido.log")

        if not any(
            isinstance(handler, logging.FileHandler) for handler in self.logger.handlers
        ):
            self.file_handler = logging.FileHandler(log_file_path)
            formatter = logging.Formatter(
                "%(asctime)s:%(levelname)s:%(name)s: %(message)s"
            )
            self.file_handler.setFormatter(formatter)
            self.logger.addHandler(self.file_handler)

    async def has_sufficient_stamina(self, user, required_stamina=20):
        """Check if the user has sufficient stamina to fight."""
        self.logger.info(f"Checking if {user} has sufficient stamina...")
        stamina = await self.config.user(user).stamina_level()
        return stamina >= required_stamina

    async def add_permanent_injury(self, user: discord.Member, injury, body_part):
        """Add a permanent injury to a user."""
        user_data = self.user_config[str(user.id)]
        if "permanent_injuries" not in user_data:
            user_data["permanent_injuries"] = []
        user_data["permanent_injuries"].append(f"{injury}")
        self.logger.info(f"Adding permanent injury {injury} to {user}.")
        await self.bullshido_cog.config.user(user).permanent_injuries.set(
            user_data["permanent_injuries"]
        )

    async def get_permanent_injuries(self, user: discord.Member):
        """Get the list of permanent injuries for a user."""
        self.logger.info(f"Getting permanent injuries for {user}.")
        return await self.config.user(user).permanent_injuries()

    async def remove_permanent_injury(
        self, user: discord.Member, injury: str, body_part: str
    ):
        """Remove a permanent injury from a user."""
        self.logger.info(f"Removing permanent injury {injury} from {user}.")
        async with self.config.user(user).permanent_injuries() as injuries:
            if body_part in injuries and injury in injuries[body_part]:
                injuries[body_part].remove(injury)

    def is_admin_or_mod():
        async def predicate(ctx):
            if isinstance(ctx, commands.Context):
                # Handling normal text commands
                return (
                    ctx.author.guild_permissions.administrator
                    or ctx.author.guild_permissions.manage_guild
                )
            elif isinstance(ctx, Interaction):
                # Handling slash commands
                return (
                    ctx.user.guild_permissions.administrator
                    or ctx.user.guild_permissions.manage_guild
                )
            return False

        return commands.check(predicate)

    async def add_xp(self, user: discord.Member, xp: int, channel: discord.TextChannel):
        """Add xp to the user config for the fight result and call check_level_up. If check_level_up returns True, call level_up"""
        user_data = await self.config.user(user).all()
        new_xp = user_data["xp"] + xp
        self.logger.debug(f"Adding {xp} xp to {user}. New total: {new_xp}")
        await self.config.user(user).xp.set(new_xp)

        if await self.check_level_up(user, new_xp, channel):
            await self.level_up(user, channel)

    async def check_level_up(
        self, user: discord.Member, new_xp: int, channel: discord.TextChannel
    ):
        """Check if the users new_xp reaches the next level, if so, return True"""
        user_data = await self.config.user(user).all()
        current_level = user_data["level"]
        self.logger.debug(f"Checking if {user} has leveled up...")
        try:
            next_level_xp = XP_REQUIREMENTS.get(current_level + 1)
            self.logger.debug(f"Next level xp: {next_level_xp}")
        except KeyError:
            self.logger.debug(
                f"Could not find next level xp for level {current_level + 1}."
            )

        if next_level_xp and new_xp >= next_level_xp:
            self.logger.info(f"{user} has leveled up!")
            return True
        return False

    async def level_up(self, user: discord.Member, channel: discord.TextChannel):
        """Increase the user level in the config and grant them level points to distribute."""
        user_data = await self.config.user(user).all()
        new_level = user_data["level"] + 1
        new_points = 1

        await self.config.user(user).level.set(new_level)
        await self.config.user(user).level_points_to_distribute.set(
            user_data["level_points_to_distribute"] + new_points
        )

        if channel:
            embed = discord.Embed(
                title="Level Up!",
                description=f"{user.mention}, you have leveled up to level {new_level}!\nYou have {new_points} new points to distribute.",
                color=discord.Color.red(),
            )
            await channel.send(embed=embed)
            await self.prompt_stat_increase(user, channel)

    async def prompt_stat_increase(
        self, user: discord.Member, channel: discord.TextChannel
    ):
        """Present the user with UI buttons to select their stat increase."""
        self.logger.info(f"Prompting {user} to increase a stat.")
        embed = discord.Embed(
            title="Learning from your epic battles in the Bullshido Kumite, your power grows!",
            description="Choose a stat to increase:",
            color=discord.Color.red(),
        )
        view = StatIncreaseView(self, user)
        await channel.send(embed=embed, view=view)

    async def increase_stat(
        self, interaction: discord.Interaction, user: discord.Member, stat: str
    ):
        """Increase the user bonus stat for their selection"""
        user_data = await self.config.user(user).all()
        points_to_distribute = user_data["level_points_to_distribute"]

        self.logger.info(f"Increasing {stat} for {user}.")
        if points_to_distribute > 0:
            if stat == "stamina":
                user_data["stamina_bonus"] += 10
                result = f"{user.mention} has chosen to increase their stamina. They will be more consistent in battle!"
            elif stat == "health":
                user_data["health_bonus"] += 10
                result = f"{user.mention} has chosen to increase their health. They will be more resilient in battle!"
            elif stat == "damage":
                user_data["damage_bonus"] += 1
                result = f"{user.mention} has chosen to increase their damage. Their strikes have become more powerful in battle!"
            else:
                return "Invalid stat."
            await interaction.response.send_message(result, ephemeral=False)
            user_data["level_points_to_distribute"] -= 1
            self.logger.info(f"{user} has increased their {stat}.")
            await self.config.user(user).set(user_data)
        else:
            await interaction.response.send_message(
                f"{user.mention}, you have no points to distribute.", ephemeral=False
            )

    def create_xp_bar(self, current_xp, current_level, next_level_xp):
        self.logger.debug(
            f"Creating xp bar for user at level {current_level} with {current_xp} xp."
        )
        previous_level_xp = XP_REQUIREMENTS.get(current_level)
        next_level = current_level + 1

        if next_level_xp is None:
            self.logger.debug("User is at max level.")
            xp_range = current_xp - previous_level_xp
            xp_progress = xp_range
            progress = 1
        else:
            self.logger.debug(
                f"User is at level {current_level}. Next level: {next_level_xp}"
            )
            xp_range = next_level_xp - previous_level_xp
            xp_progress = current_xp - previous_level_xp
            progress = xp_progress / xp_range if xp_range > 0 else 0

        progress_bar_length = 30
        progress_bar_filled = int(progress * progress_bar_length)
        progress_bar = "[" + ("=" * progress_bar_filled)
        progress_bar += (
            "=" * (progress_bar_length - progress_bar_filled)
            + "]"
            + "Level:"
            + str(next_level)
        )
        if progress_bar_filled < progress_bar_length:
            marker = "🔴"
            progress_bar = (
                progress_bar[:progress_bar_filled]
                + marker
                + progress_bar[progress_bar_filled + 1 :]
            )
        return progress_bar

    async def set_fighting_style(
        self, interaction: discord.Interaction, new_style: str
    ):
        user = interaction.user
        user_data = await self.config.user(user).all()

        if user_data["fighting_style"] != new_style:
            user_data["fighting_style"] = new_style
            user_data["training_level"] = 0
            await self.config.user(user).set(user_data)
            await self.config.user(user).fighting_style.set(new_style)
            await self.config.user(user).training_level.set(0)
            self.logger.info(f"{user} has changed their fighting style to {new_style}.")
            result = (
                f"Fighting style changed to {new_style} and training level reset to 0."
            )
        else:
            self.logger.warning(f"{user} already has the fighting style {new_style}.")
            result = "You already have this fighting style."

        await interaction.response.send_message(result)

    async def check_inactivity(self):
        self.logger.info("Checking for inactivity...")
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self.apply_inactivity_penalties()
            await asyncio.sleep(3600)  # Check every hour

    async def apply_inactivity_penalties(self):
        self.logger.info("Applying inactivity penalties...")
        current_time = datetime.utcnow() 
        users = await self.config.all_users()
        for user_id, user_data in users.items():
            self.logger.info(f"Applying inactivity penalties for user {user_id}")
            await self.apply_penalty(
                user_id, user_data, current_time, "train", "training_level"
            )
            await self.apply_penalty(
                user_id, user_data, current_time, "diet", "nutrition_level"
            )

    async def apply_penalty(
        self, user_id, user_data, current_time, last_action_key, level_key
    ):
        last_action = user_data.get(f"last_{last_action_key}")
        if last_action:
            last_action_time = datetime.strptime(last_action, "%Y-%m-%d %H:%M:%S")
            # Calculate how many full 48-hour periods have passed since last action
            time_diff = current_time - last_action_time
            missed_periods = time_diff.days // 2  # 2 days = 48 hours
            if missed_periods > 0:
                # Apply penalty for each missed period
                penalty = 20 * missed_periods
                new_level = max(1, user_data[level_key] - penalty)
                await self.config.user_from_id(user_id)[level_key].set(new_level)
                self.logger.info(
                    f"User {user_id} has lost {penalty} points in their {level_key.replace('_', ' ')} due to {missed_periods} missed 48-hour periods."
                )
                user = self.bot.get_user(user_id)
                if user:
                    await user.send(
                        f"You've lost {penalty} points in your {level_key.replace('_', ' ')} due to inactivity ({missed_periods} missed 48-hour periods)."
                    )
                # Update last_action time to the most recent penalty time
                new_last_action_time = last_action_time + timedelta(days=missed_periods * 2)
                await self.config.user_from_id(user_id)[f"last_{last_action_key}"].set(
                    new_last_action_time.strftime("%Y-%m-%d %H:%M:%S")
                )

    async def update_intimidation_level(self, user: discord.Member):
        self.logger.info(f"Updating intimidation level for {user}")
        user_data = await self.config.user(user).all()
        ko_wins = user_data["wins"]["KO"]
        tko_wins = user_data["wins"]["TKO"]
        ko_losses = user_data["losses"]["KO"]
        tko_losses = user_data["losses"]["TKO"]
        intimidation_level = ko_wins + tko_wins - ko_losses - tko_losses
        self.logger.info(f"Intimidation level for {user} is {intimidation_level}")
        await self.config.user(user).intimidation_level.set(intimidation_level)

    @commands.hybrid_group(
        name="bullshido", description="Commands related to the Bullshido game"
    )
    async def bullshido_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bullshido_help)

    @commands.hybrid_group(
        name="bullshidoset", description="Configuration commands for the Bullshido game"
    )
    async def bullshidoset_group(self, ctx: commands.Context):
        """Display Bullshido settings."""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="Bullshido Settings",
                description="Cog Settings",
                color=discord.Color.red(),
            )

            embed.set_thumbnail(url="https://i.ibb.co/7KK90YH/bullshido.png")
            embed.add_field(
                name="About",
                value="Another action packed discord cog by Slurms Mackenzie/ropeadope62\n Use [p]bullshidoset for admin commands!",
                inline=True,
            )
            embed.add_field(
                name="Repo",
                value="If you liked this, check out my other cogs! https://github.com/ropeadope62/discordcogs",
                inline=True,
            )
            embed.add_field(
                name="Rounds:",
                value=f"{await self.config.guild(ctx.guild).rounds()}",
                inline=False,
            )
            embed.add_field(
                name="Max Strikes per Round:",
                value=f"{await self.config.guild(ctx.guild).max_strikes_per_round()}",
                inline=False,
            )
            embed.add_field(
                name="Training Weight:",
                value=f"{await self.config.guild(ctx.guild).training_weight()}",
                inline=False,
            )
            embed.add_field(
                name="Diet Weight:",
                value=f"{await self.config.guild(ctx.guild).diet_weight()}",
                inline=False,
            )
            embed.add_field(
                name="Damage Bonus Weight:",
                value=f"{await self.config.guild(ctx.guild).damage_bonus_weight()}",
                inline=False,
            )
            embed.add_field(
                name="Base Health:",
                value=f"{await self.config.guild(ctx.guild).base_health()}",
                inline=False,
            )
            embed.add_field(
                name="Action Cost:",
                value=f"{await self.config.guild(ctx.guild).action_cost()}",
                inline=False,
            )
            embed.add_field(
                name="Base Miss Probability:",
                value=f"{await self.config.guild(ctx.guild).base_miss_probability()}",
                inline=False,
            )
            embed.add_field(
                name="Base Stamina Cost:",
                value=f"{await self.config.guild(ctx.guild).base_stamina_cost()}",
                inline=False,
            )
            embed.add_field(
                name="Critical Hit Chance:",
                value=f"{await self.config.guild(ctx.guild).critical_chance()}",
                inline=False,
            )
            embed.add_field(
                name="Permanent Injury Chance:",
                value=f"{await self.config.guild(ctx.guild).permanent_injury_chance()}",
                inline=False,
            )
            embed.add_field(
                name="Socialized Medicine:",
                value=f"{await self.config.guild(ctx.guild).socialized_medicine()}",
                inline=False,
            )

            await ctx.send(embed=embed)

    @bullshidoset_group.command(
        name="socializedmedicine", description="Enable or disable socialized medicine."
    )
    @commands.is_owner()
    async def toggle_socialized_medicine(
        self, ctx, single_payer: discord.Member = None
    ):
        """Toggle payment mode for treating injuries."""
        guild = ctx.guild
        current_mode = await self.config.guild(guild).socialized_medicine()

        if current_mode:
            await self.config.guild(guild).socialized_medicine.set(False)
            await self.config.guild(guild).socialized_medicine_payer_id.set(None)
            await ctx.send(f"Payment mode set to individual payment by each user.")
            self.logger.info(f"Socialized medicine mode disabled.")
        else:
            if not single_payer:
                await ctx.send(
                    "You need to mention a user who will be the single payer."
                )
                return
            await self.config.guild(guild).socialized_medicine.set(True)
            await self.config.guild(guild).socialized_medicine_payer_id.set(
                single_payer.id
            )
            await ctx.send(
                f"New provider of socialized medicine: {single_payer.display_name}."
            )
            self.logger.info(
                f"Socialized medicine mode enabled with {single_payer} as the payer."
            )

    @bullshidoset_group.command(
        name="rounds", description="Set the number of rounds in a fight."
    )
    @commands.is_owner()
    async def set_rounds(self, ctx: commands.Context, rounds: int):
        """Set the number of rounds in a fight."""
        await self.config.guild(ctx.guild).rounds.set(rounds)
        self.logger.info(f"Number of rounds set to {rounds}.")
        await ctx.send(f"Number of rounds set to {rounds}.")

    @bullshidoset_group.command(
        name="critical_chance", description="Set the critical hit chance."
    )
    @commands.is_owner()
    async def set_critical_chance(self, ctx: commands.Context, critical_chance: float):
        """Set the critical hit chance."""
        await self.config.guild(ctx.guild).critical_chance.set(critical_chance)
        self.logger.info(f"Critical hit chance set to {critical_chance}.")
        await ctx.send(f"Critical hit chance set to {critical_chance}.")

    @bullshidoset_group.command(
        name="damage_bonus_weight", description="Set the weight for damage bonus factored into damage calculations."
    )
    @commands.is_owner()
    async def set_damage_bonus_weight(self, ctx: commands.Context, damage_bonus_weight: float):
        """Set the damage bonus weight to calculate scaled damage bonuses."""
        await self.config.guild(ctx.guild).damage_bonus_weight.set(damage_bonus_weight)
        self.logger.info(f"Damage Bonus weight {damage_bonus_weight}.")
        await ctx.send(f"Damage Bonus weight set to {damage_bonus_weight}.")

    @bullshidoset_group.command(
        name="permanent_injury_chance", description="Set the permanent injury chance."
    )
    @commands.is_owner()
    async def set_permanent_injury_chance(
        self, ctx: commands.Context, permanent_injury_chance: float
    ):
        """Set the permanent injury chance. Permanent injuries occur upon critical hits."""
        await self.config.guild(ctx.guild).permanent_injury_chance.set(
            permanent_injury_chance
        )
        self.logger.info(f"Permanent injury chance set to {permanent_injury_chance}.")
        await ctx.send(f"Permanent injury chance set to {permanent_injury_chance}.")

    @bullshidoset_group.command(
        name="max_strikes_per_round",
        description="Set the maximum number of strikes per round.",
    )
    @commands.is_owner()
    async def set_max_strikes_per_round(
        self, ctx: commands.Context, max_strikes_per_round: int
    ):
        """Set the maximum number of strikes per player per round."""
        await self.config.guild(ctx.guild).max_strikes_per_round.set(
            max_strikes_per_round
        )
        self.logger.info(
            f"Maximum number of strikes per round set to {max_strikes_per_round}."
        )
        await ctx.send(
            f"Maximum number of strikes per round set to {max_strikes_per_round}."
        )

    @bullshidoset_group.command(
        name="training_weight", description="Set the training weight."
    )
    @commands.is_owner()
    async def set_training_weight(self, ctx: commands.Context, training_weight: float):
        """Set the player training weight. This is used to calculate adjusted damage in the fight."""
        await self.config.guild(ctx.guild).training_weight.set(training_weight)
        self.logger.info(f"Training weight set to {training_weight}.")
        await ctx.send(f"Training weight set to {training_weight}.")

    @bullshidoset_group.command(name="diet_weight", description="Set the diet weight.")
    @commands.is_owner()
    async def set_diet_weight(self, ctx: commands.Context, diet_weight: float):
        """Set the player diet weight. This is used to calculated adjusted damage in the fight."""
        await self.config.guild(ctx.guild).diet_weight.set(diet_weight)
        self.logger.info(f"Diet weight set to {diet_weight}.")
        await ctx.send(f"Diet weight set to {diet_weight}.")

    @bullshidoset_group.command(
        name="base_health", description="Set the maximum health."
    )
    @commands.is_owner()
    async def set_base_health(self, ctx: commands.Context, base_health: int):
        """Set the player base health."""
        await self.config.guild(ctx.guild).base_health.set(base_health)
        self.logger.info(f"Base health set to {base_health}.")
        await ctx.send(f"Base health set to {base_health}.")

    @bullshidoset_group.command(name="action_cost", description="Set the action cost.")
    @commands.is_owner()
    async def set_action_cost(self, ctx: commands.Context, action_cost: int):
        """Set the action cost per strike before modifiers."""
        await self.config.guild(ctx.guild).action_cost.set(action_cost)
        self.logger.info(f"Action cost set to {action_cost}.")
        await ctx.send(f"Action cost set to {action_cost}.")

    @bullshidoset_group.command(
        name="base_miss_probability", description="Set the base miss probability."
    )
    @commands.is_owner()
    async def set_base_miss_probability(
        self, ctx: commands.Context, base_miss_probability: float
    ):
        """Set the base miss probability per strike before modifiers."""
        await self.config.guild(ctx.guild).base_miss_probability.set(
            base_miss_probability
        )
        self.logger.info(f"Base miss probability set to {base_miss_probability}.")
        await ctx.send(f"Base miss probability set to {base_miss_probability}.")

    @bullshidoset_group.command(
        name="base_stamina_cost", description="Set the base stamina cost."
    )
    @commands.is_owner()
    async def set_base_stamina_cost(
        self, ctx: commands.Context, base_stamina_cost: int
    ):
        """Set the base stamina cost per strike before modifiers."""
        await self.config.guild(ctx.guild).base_stamina_cost.set(base_stamina_cost)
        self.logger.info(f"Base stamina cost set to {base_stamina_cost}.")
        await ctx.send(f"Base stamina cost set to {base_stamina_cost}.")

    @bullshido_group.command(name="log", description="Displays the log")
    @commands.is_owner()
    async def show_log(self, ctx: commands.Context):
        """Displays the Bullshido log."""
        logs = self.memory_handler.get_logs()
        if not logs:
            await ctx.send("No logs available.")
            return
        for chunk in [logs[i : i + 10] for i in range(0, len(logs), 10)]:
            await ctx.send("```\n{}\n```".format("\n".join(chunk)))

    @bullshidoset_group.command(
        name="set_level", description="Grant a specific level to a user."
    )
    @commands.is_owner()
    async def set_level(self, ctx: commands.Context, user: discord.Member, level: int):
        """Set a specific level to a user."""
        user_data = await self.config.user(user).all()
        current_level = user_data["level"]
        levels_gained = level - current_level
        user_data["level"] = level
        user_data["xp"] = XP_REQUIREMENTS[level] if level in XP_REQUIREMENTS else 0
        if levels_gained > 0:
            self.logger.info(f"Granting {levels_gained} levels to {user}.")
            self.logger.info(
                f"Setting {user_data['level_points_to_distribute']} points to distribute to user {user}."
            )
            user_data["level_points_to_distribute"] += levels_gained
        else:
            self.logger.info(f"Removing {levels_gained} levels from {user}.")
            self.logger.info(
                f"Setting {user_data['level_points_to_distribute']} points to distribute to user {user}."
            )
            user_data["level_points_to_distribute"] = 0

        await self.config.user(user).set(user_data)
        self.logger.info(f"Granted level {level} to {user}.")
        await ctx.send(
            f"Set {user.display_name} to level {level} with {user_data['level_points_to_distribute']} points to distribute."
        )

    @bullshidoset_group.command(
        name="reset_level", description="Reset a user's level to 1."
    )
    @commands.is_owner()
    async def reset_level(self, ctx: commands.Context, user: discord.Member):
        """Reset a user's level to 1."""
        user_data = await self.config.user(user).all()
        user_data["level"] = 1
        user_data["xp"] = 0
        user_data["level_points_to_distribute"] = 0
        user_data["stamina_bonus"] = 0
        user_data["health_bonus"] = 0
        user_data["damage_bonus"] = 0
        await self.config.user(user).set(user_data)
        self.logger.info(f"Reset {user} to level 1.")
        await ctx.send(f"Reset {user.display_name} to level 1.")

    @bullshidoset_group.command(
        name="set_player_stats", description="Manually set the users bonus stats."
    )
    @commands.is_owner()
    async def set_player_stats(
        self,
        ctx: commands.Context,
        user: discord.Member,
        stamina_bonus: int,
        health_bonus: int,
        damage_bonus: int,
    ):
        """Manually set the users bonus stats."""
        user_data = await self.config.user(user).all()
        user_data["stamina_bonus"] = stamina_bonus
        user_data["health_bonus"] = health_bonus
        user_data["damage_bonus"] = damage_bonus
        await self.config.user(user).set(user_data)
        self.logger.info(
            f"Set {user}'s stats to {stamina_bonus} stamina, {health_bonus} health, and {damage_bonus} damage."
        )
        await ctx.send(
            f"Set {user.display_name}'s stats to {stamina_bonus} stamina, {health_bonus} health, and {damage_bonus} damage."
        )

    @bullshido_group.command(
        name="challenge", description="Challenge another player to a fight with a bet."
    )
    async def challenge(
        self, ctx: commands.Context, opponent: discord.Member, bet: int
    ):
        """Challenge another player to a fight with a bet."""
        challenger = ctx.author
        currency = await bank.get_currency_name(ctx.guild)

        # Check if the challenger has enough credits
        if not await bank.can_spend(challenger, bet):
            await ctx.send(
                f"{challenger.mention}, you don't have enough {currency} to place this bet."
            )
            return

        # Check if the opponent has enough credits
        if not await bank.can_spend(opponent, bet):
            await ctx.send(
                f"{opponent.mention} doesn't have enough {currency} to place this bet."
            )
            return

        # Send the challenge message
        challenge_message = await ctx.send(
            f"{opponent.mention}, you have been challenged by {challenger.mention} to a fight who has put up {bet} {currency}. Do you accept? (yes/no)"
        )

        def check(m):
            return (
                m.author == opponent
                and m.channel == ctx.channel
                and m.content.lower() in ["yes", "no"]
            )

        try:
            # Wait for the opponent to accept or decline the challenge
            response = await self.bot.wait_for("message", check=check, timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.send(f"{opponent.mention} did not respond to the challenge...")
            return

        if response.content.lower() == "no":
            await ctx.send(f"{opponent.mention} declined the challenge...")
            return

        # Deduct the bet amount from both users
        await bank.withdraw_credits(challenger, bet)
        await bank.withdraw_credits(opponent, bet)

        # Store the total pot
        pot = bet * 2

        # Start the fight
        fighting_game = FightingGame(
            self.bot,
            ctx.channel,
            challenger,
            opponent,
            await self.config.user(challenger).all(),
            await self.config.user(opponent).all(),
            self,
            wager=bet,
            challenge=True,
        )
        await fighting_game.start_game(ctx)

        # Determine the winner and transfer the pot
        winner = fighting_game.winner

        if winner is None:
            await ctx.send(
                "The fight ended in a draw. The bet is returned to both players."
            )
            await bank.deposit_credits(challenger, bet)
            await bank.deposit_credits(opponent, bet)
        else:
            loser = opponent if winner == challenger else challenger
            await bank.deposit_credits(winner, pot)
            await ctx.send(
                f"{winner.mention} wins the fight and takes the pot of {pot} {currency}!"
            )

            # Update prize money won and lost
            await self.config.user(winner).prize_money_won.set(
                await self.config.user(winner).prize_money_won() + pot
            )
            await self.config.user(loser).prize_money_lost.set(
                await self.config.user(loser).prize_money_lost() + bet
            )

    @bullshido_group.command(
        name="hype", description="Hype the fight between two opponents."
    )
    async def hype_fight(
        self,
        ctx,
        fighter1: discord.Member,
        fighter2: discord.Member,
        wager: int = 0,
        challenge: bool = False,
    ):
        await ctx.defer()
        self.logger.info(f"Generating hype between {fighter1} and {fighter2}.")
        fighter1_id = fighter1.id
        fighter2_id = fighter2.id

        user_config = {}

        fighter1_data = await self.config.user_from_id(fighter1_id).all()
        fighter2_data = await self.config.user_from_id(fighter2_id).all()

        if not fighter1_data or not fighter2_data:
            await ctx.send("Invalid fighter ID.")
            return

        # Update names from Discord API
        fighter1_data["name"] = fighter1.display_name
        fighter2_data["name"] = fighter2.display_name

        user_config[str(fighter1_id)] = fighter1_data
        user_config[str(fighter2_id)] = fighter2_data

        if challenge:
            narrative = generate_hype_challenge(
                user_config,
                fighter1_id,
                fighter2_id,
                fighter1.display_name,
                fighter2.display_name,
                wager,
            )
        else:
            narrative = generate_hype(
                user_config,
                fighter1_id,
                fighter2_id,
                fighter1.display_name,
                fighter2.display_name,
            )

        embed = discord.Embed(
            title=f"{fighter1_data['name']} vs {fighter2_data['name']}",
            description=narrative,
            color=0xFF0000,
        )

        await ctx.send(embed=embed)

    @bullshido_group.command(
        name="top_injuries",
        description="List the players with the 10 most permanent injuries",
    )
    async def top_injuries(self, ctx: commands.Context):
        """Lists the players with the 10 most permanent injuries."""
        users = await self.config.all_users()
        injury_counts = []
        self.logger.info("Getting top 10 players with most permanent injuries.")
        for user_id, user_data in users.items():
            permanent_injuries = user_data.get("permanent_injuries", [])
            injury_count = len(permanent_injuries)
            injury_counts.append((user_id, injury_count))

        # Sort by injury count in descending order and take the top 10
        injury_counts = sorted(injury_counts, key=lambda x: x[1], reverse=True)[:10]

        if not injury_counts:
            await ctx.send("No permanent injuries found.")
            return

        embed = discord.Embed(
            title="Top 10 Players with Most Permanent Injuries", color=0xFF0000
        )
        embed.set_thumbnail(url="https://i.ibb.co/7KK90YH/bullshido.png")

        for i, (user_id, count) in enumerate(injury_counts, 1):
            user = self.bot.get_user(user_id)
            if user:
                embed.add_field(
                    name=f"{i}. {user.display_name}",
                    value=f"Injuries: {count}",
                    inline=False,
                )

        await ctx.send(embed=embed)

    @bullshido_group.command(
        name="distribute_points",
        description="If you have unspent level points to distribute, spend them on bonuses.",
    )
    async def distribute_points(self, ctx: commands.Context):
        user = ctx.author
        points_to_distribute = await self.config.user(user).level_points_to_distribute()

        if points_to_distribute > 0:
            await self.prompt_stat_increase(user, ctx.channel)
        else:
            await ctx.send(f"{user.mention}, you don't have any points to distribute.")

    @bullshido_group.command(
        name="injuries",
        description="View your permanent injuries that require treatment.",
        aliases=["injury", "inj"],
    )
    async def permanent_injuries(
        self, ctx: commands.Context, user: discord.Member = None
    ):
        """View your permanent injuries that require treatment."""
        if not user:
            user = ctx.author
        user_data = await self.config.user(user).all()
        permanent_injuries = user_data.get("permanent_injuries", [])
        self.logger.info(f"Getting permanent injuries for {user}.")

        if not permanent_injuries:
            await ctx.send("You have no permanent injuries.")
            return

        embed = discord.Embed(
            title=f"{user.display_name}'s Permanent Injuries", color=0xFF0000
        )
        embed.add_field(
            name="Injuries", value=", ".join(permanent_injuries), inline=False
        )

        embed.set_thumbnail(url="https://i.ibb.co/7KK90YH/bullshido.png")
        await ctx.send(embed=embed)

    @bullshido_group.command(name="treat", description="Treat a permanent injury")
    async def treat_injury(self, ctx, *, injury: str):
        """Treat specific injury for a user."""
        guild = ctx.guild
        user = ctx.author
        socialized_medicine_mode = await self.config.guild(guild).socialized_medicine()
        socialized_medicine_payer_id = await self.config.guild(
            guild
        ).socialized_medicine_payer_id()
        currency = await bank.get_currency_name(ctx.guild)

        user_data = await self.config.user(user).all()
        permanent_injuries = user_data.get("permanent_injuries", [])

        if injury not in permanent_injuries:
            await ctx.send(
                f"{user.display_name} does not have the specified injury: {injury}."
            )
            self.logger.warning(f"{user} does not have the specified injury: {injury}.")
            return

        cost = INJURY_TREATMENT_COST.get(injury)
        if not cost:
            await ctx.send(f"The specified injury: {injury} is not recognized.")
            self.logger.warning(f"The specified injury: {injury} is not recognized.")
            return

        if socialized_medicine_mode:
            socialized_medicine_payer = guild.get_member(socialized_medicine_payer_id)
            if socialized_medicine_mode:
                await bank.withdraw_credits(socialized_medicine_payer, cost)
                self.logger.info(
                    f"{socialized_medicine_payer} has paid {cost} {currency} for treating {user}'s {injury}."
                )
                await ctx.send(
                    f"Through socialized medicine, {socialized_medicine_payer.display_name} has paid {cost} {currency} for treating {user.display_name}'s {injury}."
                )
            else:
                self.logger.warning(
                    "Socialized medicine payer is not found. Please reconfigure the payment mode."
                )
                await ctx.send(
                    "Socialized medicine payer is not found. Please reconfigure the payment mode."
                )
                return
        else:
            await bank.withdraw_credits(user, cost)
            self.logger.info(
                f"{user} has paid {cost} {currency} for their own {injury} treatment."
            )
            await ctx.send(
                f"{user.display_name} has paid {cost} {currency} for their own {injury} treatment."
            )

        # Code to remove the specified injury from user config
        permanent_injuries.remove(injury)
        await self.config.user(user).permanent_injuries.set(permanent_injuries)
        self.logger.info(f"{user} has successfully treated their {injury}.")
        await ctx.send(f"{user.display_name}'s {injury} has been successfully treated.")

    @bullshido_group.command(
        name="rankings",
        description="Top fighters in the Bullshido Kumatae.",
        aliases=["rank", "leaderboard", "lb"],
    )
    async def rankings(self, ctx: commands.Context):
        """Displays the top 25 players based on win-loss ratio and their fight record."""
        self.logger.info("Getting the top 25 players based on win-loss ratio.")
        server_name = ctx.guild.name
        users = await self.config.all_users()
        ranking_list = []

        for user_id, user_data in users.items():
            wins = sum(user_data["wins"].values())
            losses = sum(user_data["losses"].values())
            if wins == 0 and losses == 0:
                continue  # Skip players with no fights
            if losses == 0:
                win_loss_ratio = wins  # Avoid division by zero
            else:
                win_loss_ratio = wins / losses

            ranking_list.append((user_id, wins, losses, win_loss_ratio))

            # Sort the list by win-loss ratio in descending order and take the top 25
        ranking_list = sorted(ranking_list, key=lambda x: x[3], reverse=True)[:25]

        embed = discord.Embed(title=f"{server_name} Bullshido Rankings", color=0xFF0000)
        embed.set_thumbnail(url="https://i.ibb.co/7KK90YH/bullshido.png")

        for i, (user_id, wins, losses, ratio) in enumerate(ranking_list, 1):
            user = self.bot.get_user(user_id)
            if user:
                embed.add_field(
                    name=f"{i}. {user.display_name}",
                    value=f"Wins: {wins}, Losses: {losses}",
                    inline=False,
                )

        await ctx.send(embed=embed)

    @bullshido_group.command(name="setstyle", description="Select your fighting style")
    async def select_fighting_style(self, ctx: commands.Context):
        """Prompts the user to select their fighting style."""
        view = SelectFightingStyleView(self.set_fighting_style, ctx.author, ctx)
        self.logger.info(f"Prompting {ctx.author} to select their fighting style.")
        await ctx.send("Please select your fighting style:", view=view)

    @bullshido_group.command(
        name="list_fighting_styles", description="List all available fighting styles"
    )
    async def list_fighting_styles(self, ctx: commands.Context):
        """List all available fighting styles."""
        styles = list(STRIKES.keys())
        embed = discord.Embed(
            title="Available Fighting Styles",
            description="\n".join(styles),
            color=0xFF0000,
        )
        embed.set_thumbnail(url="https://i.ibb.co/7KK90YH/bullshido.png")
        self.logger.info(f"Listing available fighting styles.")
        await ctx.send(embed=embed)

    @bullshido_group.command(
        name="fight", description="Start a fight with another player"
    )
    async def fight(self, ctx: commands.Context, opponent: discord.Member):
        """Start a fight with another player."""
        await ctx.defer()
        self.logger.info(f"{ctx.author} challenged {opponent} to a fight.")
        try:
            player1, player2 = ctx.author, opponent
            player1_data, player2_data = await self.get_player_data(player1), await self.get_player_data(player2)

            if not await self.validate_fight_conditions(ctx, player1, player2, player1_data, player2_data):
                return

            game = FightingGame(
                self.bot,
                ctx.channel,
                player1,
                player2,
                player1_data,
                player2_data,
                self,
            )
            game.user_config = {
                str(player1.id): player1_data,
                str(player2.id): player2_data,
            }

            await game.start_game(ctx)
            self.logger.info("Game started successfully.")

        except Exception as e:
            self.logger.error(f"Failed to start fight: {e}")
            await ctx.send(f"Failed to start the fight due to an error: {e}")

    async def validate_fight_conditions(self, ctx, player1, player2, player1_data, player2_data):
        """Validate conditions before starting a fight."""
        if not await self.has_sufficient_stamina(player1):
            await ctx.send(
                f"You are too tired to fight, {player1.mention}.\nTry waiting some time for your stamina to recover, or buy some supplements to speed up your recovery."
            )
            self.logger.warning(f"{player1} does not have enough stamina to fight.")
            return False
        if not await self.has_sufficient_stamina(player2):
            await ctx.send(
                "Your opponent does not have enough stamina to start the fight."
            )
            self.logger.warning(f"{player2} does not have enough stamina to fight.")
            return False

        if not player1_data["fighting_style"]:
            await ctx.send(
                f"{player1.display_name}, you need to select a fighting style before you can fight."
            )
            self.logger.info(f"{player1} does not have a fighting style selected.")
            return False
        if not player2_data["fighting_style"]:
            await ctx.send(
                f"{player2.display_name} needs to select a fighting style before they can fight."
            )
            self.logger.info(f"{player2} does not have a fighting style selected.")
            return False

        if player1 == player2:
            await ctx.send(
                "You cannot fight yourself, only your own demons! Try challenging another fighter."
            )
            self.logger.warning(f"{player1} tried to fight themselves.")
            return False

        return True

    @bullshido_group.command(
        name="train",
        description="Train daily to increase your Bullshido training level",
    )
    async def train(self, ctx: commands.Context):
        """Train daily to increase your Bullshido training level."""
        self.logger.info(f"{ctx.author} used the train command.")
        user = ctx.author
        style = await self.config.user(user).fighting_style()
        if style is None:
            await ctx.send(
                f"{user.mention}, you need to select a fighting style before you can train."
            )
            return
        # Check if the command was used in the last 24 hours
        last_train = await self.config.user(user).last_train()
        if last_train:
            last_train_time = datetime.strptime(last_train, "%Y-%m-%d %H:%M:%S")
            time_since_last_train = datetime.utcnow() - last_train_time
            if time_since_last_train < timedelta(hours=24):
                time_left = timedelta(hours=24) - time_since_last_train
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                await ctx.send(
                    f"{user.mention}, you can only use the train command once every 24 hours. Time left: {time_left.days} days, {hours} hours, and {minutes} minutes."
                )
                return

        # Update the last train time before executing the command to avoid timing issues
        await self.config.user(user).last_train.set(
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        )

        # Increment training level
        new_training_level = await self.increment_training_level(ctx)
        self.logger.info(
            f"{user} has successfully trained in {style}! Their training level is now {new_training_level}."
        )
        await ctx.send(
            f"{user.mention} has successfully trained in {style}! Your training level is now {new_training_level}."
        )

    @bullshido_group.command(
        name="diet", description="Focus on your diet to increase your nutrition level"
    )
    async def diet(self, ctx: commands.Context):
        """Focus on your diet to increase your nutrition level."""
        self.logger.info(f"{ctx.author} used the diet command.")
        user = ctx.author
        style = await self.config.user(user).fighting_style()
        if style is None:
            await ctx.send(
                f"{user.mention}, you need to select a fighting style before you can diet."
            )
            return
        # Check if the command was used in the last 24 hours
        last_diet = await self.config.user(user).last_diet()
        if last_diet:
            last_diet_time = datetime.strptime(last_diet, "%Y-%m-%d %H:%M:%S")
            time_since_last_diet = datetime.utcnow() - last_diet_time
            if time_since_last_diet < timedelta(hours=24):
                time_left = timedelta(hours=24) - time_since_last_diet
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                await ctx.send(
                    f"{user.mention}, you can only use the diet command once every 24 hours. Time left: {time_left.days} days, {hours} hours, and {minutes} minutes."
                )
                return

        # Update the last diet time before executing the command to avoid timing issues
        await self.config.user(user).last_diet.set(
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        )

        # Increment nutrition level
        new_nutrition_level = await self.increment_nutrition_level(ctx)
        await ctx.send(
            f"{user.mention} has followed their specialized diet today and gained nutrition level! Your nutrition level is now {new_nutrition_level}."
        )

    @bullshido_group.command(
        name="help", description="Learn how the Bullshido game works"
    )
    async def bullshido_help(self, ctx: commands.Context):
        """Provides information about how the Bullshido game works."""
        embed = discord.Embed(
            title="Help / About Bullshido",
            description="Welcome to Bullshido, a Discord game of epic combat!",
            color=0xFF0000,
        )
        # Basic Gameplay Commands
        embed.add_field(
            name="🎮 **Basic Gameplay Commands**",
            value=(
                "**`/bullshido fight @opponent`**: Start a fight with another player.\n"
                "**`/bullshido challenge @opponent <amount>`**: Challenge another player to a prize fight for a wager bet. The opponent must accept the challenge before the fight will begin.\n"
            ),
            inline=False,
        )

        # Fighter Customization
        embed.add_field(
            name="💪 **Fighter Customization**",
            value=(
                "**`/bullshido setstyle`**: Choose your fighting style. Options include Karate, Muay-Thai, Aikido, Boxing, Kung-Fu, Judo, Taekwondo, Wrestling, "
                "Krav-Maga, Capoeira, Sambo, Kickboxing, MMA, Brazilian Jiu-Jitsu, Zui Quan.\n"
                "**`/bullshido train`**: Increase your fighter's training level to improve performance.\n"
                "**`/bullshido diet`**: Improve your fighter's nutrition level to enhance stamina and recovery.\n"
                "**`/bullshido distribute_points`**: Spend any skill points you have been granted by advancing player level."
            ),
            inline=False,
        )

        # Game Mechanics
        embed.add_field(
            name="⚙️ **Game Mechanics**",
            value=(
                "**Health & Stamina**: Each fighter starts with a base health and stamina. Performing actions depletes stamina, "
                "which regenerates between rounds based on your training and diet levels.\n"
                "**Rounds & Scoring**: Fights typically last 3 rounds. Each round is scored using a 10-point must system. "
                "The fighter with the most points at the end of the fight wins unless a KO or TKO occurs.\n"
                "**KO & TKO**: Fights can end early if a fighter is knocked out (KO) or if the referee determines they can no longer continue (TKO). Intimidation level affects the likelihood of these outcomes."
            ),
            inline=True,
        )

        embed.add_field(
            name="🔧 **Strike Calculations**",
            value=(
                "**Strike Damage**: Damage dealt is influenced by your chosen fighting style, training level, nutrition level, and any damage bonuses.\n "
                "Critical strikes can double the damage and cause permanent injuries to your opponent. \n"
                "**Critical Hits**: Certain strikes have a chance to critically injure an opponent, causing additional damage or permanent injuries.\n"
                "**Hit Probability**: Hit chance is based on both fighter's stats and stamina levels as the fight progresses. Intimidation affects strike chance to a lesser extent.\n"
                "**Intimidation Level**: A higher intimidation level reduces your opponent's chances to land successful strikes and increases your chances of securing a KO or TKO victory.\n"
            ),
            inline=False,
        )

        # Server Interaction Mechanic
        embed.add_field(
            name="🌐 **How to Maximize your odds and Win Fights**",
            value=(
                "**Train Daily**: You can train once every 24 hours, with each consecutive day of training, your fighter will gain 10 training level\n"
                "**Diet Daily**: You can improve your diet / nutrition every 24 hours, with each consecutive day of dieting, your fighter will gain 10 diet level.\n"
                "**Don't Forget to Diet or Train!**: Training and dieting are essential to improving your fighter's performance in the ring. Your Training and Diet levels will begin to drain if you did not perform an activity for 48 hours.\n"
                "**Pick Your Opponents**: If your Training and Diet level is low against a fighter of the same level, it's likely you'll lose. If your opponent is of higher Player Level, you'll very likely lose.\n"
                "**Intimidation**: Think twice about challenging opponents with high damage bonus and a high intimidation level (compared to your own). This is how you get KTFO.\n"
            ),
        )

        # Additional Information
        embed.add_field(
            name="📜 **Additional Information**",
            value=(
                "**Permanent Injuries**: Fighters can sustain permanent injuries that affect future performance.\n"
                "**Fighting with Permanent Injuries**: Fighters can choose to fight with permanent injuries, but they will suffer double damage to injured bodyparts.\n"
                "**Checking Your Injuries**: Use the `/bullshido injuries` command to view your permanent injuries.\n"
                "**Treating Injuries**: Permanent injuries can be treated with the `/bullshido treat <injury>` command. "
            ),
            inline=False,
        )

        # Other Commands
        embed.add_field(
            name="🏆 **Stats Commands**",
            value=(
                "**`/bullshido player_stats`**: View your own fighting stats and player attributes.\n"
                "**`/bullshido player_stats @user`**: View another player's fighting stats and player attributes.\n"
                "**`/bullshido top_injuries`**: List the players with the 10 most permanent injuries.\n"
                "**`/bullshido rankings`**: Display the top 25 players based on win-loss ratio and their fight record.\n"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Bullshido is a cog by Slurms aka https://github.com/ropeadope62."
        )

        embed.set_thumbnail(url="https://i.ibb.co/GWpXztm/bullshido.png")
        await ctx.send(embed=embed)

    @bullshido_group.command(
        name="reset_stats",
        description="Resets all Bullshido user data to default values",
    )
    @commands.is_owner()
    async def reset_stats(self, ctx: commands.Context):
        """Reset the Bullshido Redbot Configuration values to default for all users."""
        self.logger.info(f"{ctx.author} used the reset_stats command.")

        def check(m):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.upper() == "YES"
            )

        # Send confirmation message
        await ctx.send(
            "Are you sure you want to reset Bullshido user data? Type 'YES' to confirm."
        )

        try:
            # Wait for a response for 30 seconds
            confirmation = await self.bot.wait_for("message", check=check, timeout=30.0)
            if confirmation:
                # If confirmed, reset all config values
                default_user = {
                    "fighting_style": None,
                    "wins": {"UD": 0, "SD": 0, "TKO": 0, "KO": 0},
                    "losses": {"UD": 0, "SD": 0, "TKO": 0, "KO": 0},
                    "level": 1,
                    "training_level": 1,
                    "nutrition_level": 1,
                    "morale": 100,
                    "intimidation_level": 0,
                    "stamina_level": 100,
                    "last_interaction": None,
                    "last_command_used": None,
                    "last_train": None,
                    "last_diet": None,
                    "fight_history": [],
                }

                async with self.config.all_users() as all_users:
                    for user_id in all_users:
                        user_config = self.config.user_from_id(user_id)
                        for key, value in default_user.items():
                            await user_config.set_raw(key, value=value)
                self.logger.info("All user stats have been reset to default.")
                await ctx.send("All config values have been reset to default.")
        except asyncio.TimeoutError:
            self.logger.warning("Reset operation cancelled due to timeout.")
            await ctx.send("Reset operation cancelled due to timeout.")

    @bullshido_group.command(
        name="reset_config",
        description="Resets Bullshido configuration to default values",
    )
    @commands.is_owner()
    async def reset_config(self, ctx: commands.Context):
        """Resets Bullshido configuration to default values."""
        await self.config.clear_all_users()
        self.logger.info(f"Cleared all user stats.")
        await ctx.send("Bullshido configuration has been reset to default values.")

    @bullshido_group.command(name="player_stats", description="Displays your or a member's wins and losses", aliases=["stats"])
    async def player_stats(self, ctx: commands.Context, user: discord.Member = None):
        """Displays your or a member's wins and losses."""
        if user is None:
            user = ctx.author
        user = ctx.author
        wins = await self.config.user(user).wins()
        losses = await self.config.user(user).losses()
        draws = await self.config.user(user).draws()
        level = await self.config.user(user).level()
        current_xp = await self.config.user(user).xp()
        next_level_xp = XP_REQUIREMENTS.get(level + 1, None)

        training_level = await self.config.user(user).training_level()
        nutrition_level = await self.config.user(user).nutrition_level()
        health_bonus = await self.config.user(user).health_bonus()
        player_health = 100 + health_bonus
        morale = await self.config.user(user).morale()
        intimidation_level = await self.config.user(user).intimidation_level()
        fighting_style = await self.config.user(user).fighting_style()
        stamina = await self.config.user(user).stamina_level()
        stamina_bonus = await self.config.user(user).stamina_bonus()
        player_stamina = stamina + stamina_bonus
        player_damage_bonus = await self.config.user(user).damage_bonus()
        level_up_points_to_distribute = await self.config.user(
            user
        ).level_points_to_distribute()
        prize_money_won = await self.config.user(user).prize_money_won()
        prize_money_lost = await self.config.user(user).prize_money_lost()

        total_wins = sum(wins.values())
        total_losses = sum(losses.values())

        xp_bar = self.create_xp_bar(current_xp, level, next_level_xp)
        xp_info = (
            f"{current_xp} / {next_level_xp} XP"
            if next_level_xp is not None
            else f"{current_xp} XP (Max Level)"
        )

        embed = discord.Embed(
            title=f"{user.display_name}'s Fight Record", color=0xFF0000
        )
        embed.add_field(name="Total Wins", value=total_wins, inline=True)
        embed.add_field(name="Total Losses", value=total_losses, inline=True)
        embed.add_field(name="Wins (UD)", value=wins["UD"], inline=True)
        embed.add_field(name="Wins (SD)", value=wins["SD"], inline=True)
        embed.add_field(name="Wins (TKO)", value=wins["TKO"], inline=True)
        embed.add_field(name="Wins (KO)", value=wins["KO"], inline=True)
        embed.add_field(name="Losses (UD)", value=losses["UD"], inline=True)
        embed.add_field(name="Losses (SD)", value=losses["SD"], inline=True)
        embed.add_field(name="Losses (TKO)", value=losses["TKO"], inline=True)
        embed.add_field(name="Losses (KO)", value=losses["KO"], inline=True)
        embed.add_field(name="Draws", value=draws, inline=True)
        embed.add_field(
            name=f"{user.display_name}'s Current Stats", value="\u200b", inline=False
        )
        embed.add_field(name="Fighting Style", value=fighting_style, inline=True)
        embed.add_field(name="Level", value=level, inline=True)
        embed.add_field(name="Training Level", value=training_level, inline=True)
        embed.add_field(name="Nutrition Level", value=nutrition_level, inline=True)
        embed.add_field(name="Health", value=player_health, inline=True)
        embed.add_field(name="Morale", value=morale, inline=True)
        embed.add_field(
            name="Intimidation Level", value=intimidation_level, inline=True
        )
        embed.add_field(name="Damage Bonus", value=player_damage_bonus, inline=True)
        embed.add_field(name="Stamina", value=player_stamina, inline=True)
        embed.add_field(
            name="Level Points to Distribute",
            value=level_up_points_to_distribute,
            inline=True,
        )
        embed.add_field(name="Prize Money Won", value=prize_money_won, inline=True)
        embed.add_field(name="Prize Money Lost", value=prize_money_lost, inline=True)
        embed.add_field(name="XP Progress", value=xp_bar, inline=False)
        embed.set_thumbnail(url="https://i.ibb.co/7KK90YH/bullshido.png")
        await ctx.send(embed=embed)

    @bullshido_group.command(
        name="fight_record", description="Displays the results of your last 10 fights"
    )
    async def fight_record(self, ctx: commands.Context):
        """Displays the results of your last 10 fights."""
        user = ctx.author
        self.logger.info(f"{ctx.author} used the fight_record command.")
        fight_history = await self.config.user(user).fight_history()

        if not fight_history:
            await ctx.send("You have no fight history.")
            return

        embed = discord.Embed(
            title=f"{user.display_name}'s Last 10 Fights", color=0xFF0000
        )

        for fight in fight_history[-10:]:
            outcome = fight.get("outcome", "Unknown")
            opponent = fight.get("opponent", "Unknown")
            result_type = fight.get("result_type", "Unknown")
            embed.add_field(
                name=f"Fight vs {opponent}",
                value=f"Outcome: {outcome}, Result: {result_type}",
                inline=False,
            )

        embed.set_thumbnail(url="https://i.ibb.co/7KK90YH/bullshido.png")
        await ctx.send(embed=embed)

    async def get_player_data(self, user):
        fighting_style = await self.config.user(user).fighting_style()
        level = await self.config.user(user).level()
        training_level = await self.config.user(user).training_level()
        nutrition_level = await self.config.user(user).nutrition_level()
        morale = await self.config.user(user).morale()
        intimidation_level = await self.config.user(user).intimidation_level()
        wins = await self.config.user(user).wins()
        losses = await self.config.user(user).losses()
        fight_history = await self.config.user(user).fight_history()
        return {
            "fighting_style": fighting_style,
            "wins": wins,
            "losses": losses,
            "level": level,
            "training_level": training_level,
            "nutrition_level": nutrition_level,
            "morale": morale,
            "intimidation_level": intimidation_level,
            "fight_history": fight_history,
        }

    async def update_player_stats(self, user, win, result_type, opponent_name):
        self.logger.debug(f"Updating stats for {user.display_name}")
        try:
            current_wins = await self.config.user(user).wins()
            current_losses = await self.config.user(user).losses()
            fight_history = await self.config.user(user).fight_history()

            outcome = "Win" if win else "Loss"

            fight_history.append(
                {
                    "opponent": opponent_name,
                    "outcome": outcome,
                    "result_type": result_type,
                }
            )

            if win:
                new_wins = current_wins.copy()
                new_wins[result_type] += 1
                await self.config.user(user).wins.set(new_wins)
                self.logger.debug(
                    f"Updated wins for {user.display_name}: {current_wins} -> {new_wins}"
                )
            else:
                new_losses = current_losses.copy()
                new_losses[result_type] += 1
                await self.config.user(user).losses.set(new_losses)
                self.logger.debug(
                    f"Updated losses for {user.display_name}: {current_losses} -> {new_losses}"
                )

            # Update the fight history
            await self.config.user(user).fight_history.set(fight_history)
            await self.update_intimidation_level(user)

        except Exception as e:
            self.logger.error(f"Error updating stats for {user.display_name}: {e}")

    @bullshido_group.command(
        name="clear_old_config",
        description="Clears old configuration to avoid conflicts",
    )
    @commands.is_owner()
    async def clear_old_config(self, ctx: commands.Context):
        """Clears old configuration to avoid conflicts."""
        await self.config.clear_all_users()
        self.logger.info(f"Cleared all user stats.")
        await ctx.send("Old Bullshido configuration has been cleared.")

    @bullshido_group.command(name="test_fight_image")
    async def display_fight_image(
        self, ctx: commands.Context, player1: discord.Member, player2: discord.Member
    ):
        self.logger.debug(
            f"Testing fight image generation between {player1} and {player2}"
        )
        try:
            # Create a dummy player data for testing
            player1_data = {
                "fighting_style": "Karate",
                "wins": {"UD": 5, "SD": 3, "TKO": 2, "KO": 1},
                "losses": {"UD": 2, "SD": 1, "TKO": 3, "KO": 4},
                "training_level": 3,
                "nutrition_level": 2,
                "morale": 80,
                "intimidation_level": 1,
                "stamina_level": 100,
                "last_interaction": None,
                "last_command_used": None,
                "last_train": None,
                "last_diet": None,
                "fight_history": [],
                "permanent_injuries": {},
            }

            player2_data = {
                "fighting_style": "Muay Thai",
                "wins": {"UD": 4, "SD": 5, "TKO": 3, "KO": 2},
                "losses": {"UD": 1, "SD": 2, "TKO": 2, "KO": 3},
                "training_level": 4,
                "nutrition_level": 3,
                "morale": 85,
                "intimidation_level": 2,
                "stamina_level": 100,
                "last_interaction": None,
                "last_command_used": None,
                "last_train": None,
                "last_diet": None,
                "fight_history": [],
                "permanent_injuries": {},
            }

            # Initialize the FightingGame instance with dummy data for testing
            game = FightingGame(
                self.bot,
                ctx.channel,
                player1,
                player2,
                player1_data,
                player2_data,
                self,
            )

            fight_image_path = await game.generate_fight_image()
            await ctx.send(file=discord.File(fight_image_path))
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    async def increment_training_level(self, ctx):
        user = ctx.author
        self.logger.info(f"Incrementing training level for {user}")
        user_data = await self.config.user(user).all()
        new_training_level = min(100, user_data["training_level"] + 10)
        if new_training_level >= 100:
            await ctx.send(
                f"{user.mention} has reached maximum training level for the next 24 hours!"
            )
        await self.config.user(user).training_level.set(new_training_level)
        self.logger.info(f"Training level for {user} is now {new_training_level}")
        return new_training_level

    async def increment_stamina_level(self, user):
        self.logger.info(f"Incrementing stamina level for {user}")
        stamina_level = await self.config.user(user).stamina_level()
        new_stamina_level = stamina_level + 10
        await self.config.user(user).training_level.set(new_stamina_level)
        self.logger.info(f"Stamina level for {user} is now {new_stamina_level}")
        return new_stamina_level

    async def increment_nutrition_level(self, ctx):
        user = ctx.author
        self.logger.info(f"Incrementing nutrition level for {user}")
        user_data = await self.config.user(user).all()
        new_nutrition_level = min(100, user_data["nutrition_level"] + 10)
        if new_nutrition_level >= 100:
            await ctx.send(
                f"{user.mention} has reached optimal nutrition for the next 24 hours!"
            )
        await self.config.user(user).nutrition_level.set(new_nutrition_level)
        self.logger.info(f"Nutrition level for {user} is now {new_nutrition_level}")
        return new_nutrition_level

    async def update_daily_interaction(self, user, command_used):
        self.logger.info(f"Updating daily interaction for {user}")
        user_data = await self.config.user(user).all()
        today = datetime.utcnow().date()

        last_interaction = user_data.get(f"last_{command_used}")
        if last_interaction:
            last_interaction_date = datetime.strptime(
                last_interaction, "%Y-%m-%d %H:%M:%S"
            ).date()
            self.logger.info(
                f"Last {command_used} interaction for {user} was on {last_interaction_date}."
            )
            if today - last_interaction_date > timedelta(days=1):
                await self.config.user(user).last_interaction.set(
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                )
                self.logger.info(f"Reset last {command_used} interaction for {user}.")
