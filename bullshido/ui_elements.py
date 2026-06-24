from discord import ui, ButtonStyle
import discord

class SelectFightingStyleView(ui.View):
    def __init__(self, on_fighting_style_selected, user, ctx):
        super().__init__(timeout=180)
        self.style_selected_callback = on_fighting_style_selected
        self.user = user
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    @ui.button(label="Karate", style=ButtonStyle.primary)
    async def handle_karate(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Karate")

    @ui.button(label="Muay-Thai", style=ButtonStyle.primary)
    async def handle_muaythai(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Muay-Thai")
    
    @ui.button(label="Aikido", style=ButtonStyle.primary)
    async def handle_aikido(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Aikido")

    @ui.button(label="Boxing", style=ButtonStyle.primary)
    async def handle_boxing(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Boxing")

    @ui.button(label="Kung-Fu", style=ButtonStyle.primary)
    async def handle_kungfu(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Kung-Fu")

    @ui.button(label="Judo", style=ButtonStyle.primary)
    async def handle_judo(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Judo")

    @ui.button(label="Taekwondo", style=ButtonStyle.primary)
    async def handle_taekwondo(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Taekwondo")

    @ui.button(label="Wrestling", style=ButtonStyle.primary)
    async def handle_wrestling(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Wrestling")

    @ui.button(label="Krav-Maga", style=ButtonStyle.primary)
    async def handle_kravmaga(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Krav-Maga")

    @ui.button(label="Capoeira", style=ButtonStyle.primary)
    async def handle_capoeira(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Capoeira")

    @ui.button(label="Sambo", style=ButtonStyle.primary)
    async def handle_sambo(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Sambo")

    @ui.button(label="Kickboxing", style=ButtonStyle.primary)
    async def handle_kickboxing(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Kickboxing")

    @ui.button(label="MMA", style=ButtonStyle.primary)
    async def handle_mma(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "MMA")
    
    @ui.button(label="Brazilian Jiu-Jitsu", style=ButtonStyle.primary)
    async def handle_bjj(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Brazilian Jiu-Jitsu")
        
    @ui.button(label="Zui Quan", style=ButtonStyle.primary)
    async def handle_zq(self, interaction: discord.Interaction, button: ui.Button):
        await self.style_selected_callback(interaction, "Zui Quan")

class StatIncreaseView(ui.View):
    def __init__(self, cog, user):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.user

    @ui.button(label="Increase Health", style=ButtonStyle.primary)
    async def increase_strength(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.increase_stat(interaction, self.user, "health")

    @ui.button(label="Increase Stamina", style=ButtonStyle.primary)
    async def increase_agility(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.increase_stat(interaction, self.user, "stamina")

    @ui.button(label="Increase Damage", style=ButtonStyle.primary)
    async def increase_stamina(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.increase_stat(interaction, self.user, "damage")