from redbot.core import commands, Config, bank
import random
import asyncio
import discord
import logging

class Deck:
    def __init__(self, num_decks=2):
        self.cards = []
        self.num_decks = num_decks  # Fixed typo from num_deks to num_decks
        self.suits = [":clubs:", ":diamonds:", ":hearts:", ":spades:"]
        self.ranks = {
            "ace": 11,
            "2": 2,
            "3": 3,
            "4": 4,
            "5": 5,
            "6": 6,
            "7": 7,
            "8": 8,
            "9": 9,
            "10": 10,
            "jack": 10,
            "queen": 10,
            "king": 10,
        }
        self.refill()

    def shuffle(self):
        random.shuffle(self.cards)
        print("Shuffled all decks...")

    def deal_card(self):
        if len(self.cards) == 0:
            print("No cards left in the deck. Refilling deck...")
            self.refill()
        return self.cards.pop()

    def refill(self):
        self.cards = []
        for _ in range(self.num_decks):
            for suit in self.suits:
                for rank, value in self.ranks.items():
                    self.cards.append(Card(suit, rank, value))
        self.shuffle()

    def num_cards_remaining(self):
        return len(self.cards)


class Card:
    def __init__(self, suit, rank, value):
        self.suit = suit
        self.rank = rank
        self.value = value
        
    def __str__(self):
        # Unicode card representation
        suits_unicode = {
            ":clubs:": "♣️",
            ":diamonds:": "♦️",
            ":hearts:": "♥️",
            ":spades:": "♠️"
        }
        rank_display = {
            "ace": "A",
            "2": "2",
            "3": "3",
            "4": "4",
            "5": "5",
            "6": "6",
            "7": "7",
            "8": "8",
            "9": "9",
            "10": "10",
            "jack": "J",
            "queen": "Q",
            "king": "K"
        }
        suit = suits_unicode[self.suit]
        rank = rank_display[self.rank]
        return f"{rank}{suit}"

    def __repr__(self):
        return f"{self.rank} of {self.suit} ({self.value})"


class Participant:
    def __init__(self):
        self.hand = []
        self.score = 0
        self.bust = False
        self.blackjack = False
        self.stands = False

    def draw_card(self, deck):
        card = deck.deal_card()
        self.hand.append(card)
        return card

    def calculate_score(self):
        for card in self.hand:
            print(f"Card in hand: {card}, Type: {type(card)}")
        self.score = sum(card.value for card in self.hand)
        aces = sum(1 for card in self.hand if card.rank == "ace")

        while self.score > 21 and aces:
            self.score -= 10
            aces -= 1

        if self.score > 21:
            self.bust = True
        elif self.score == 21:
            self.blackjack = True

    async def clear_hand(self):
        self.hand = []
        self.score = 0
        self.bust = False
        self.blackjack = False
        self.stands = False


class Player(Participant):
    def __init__(self, name, ctx):
        super().__init__()
        self.name = name  
        self.ctx = ctx
        self.bet = 0
        self.hands = [self.hand]  # Initialize hands with the main hand
        
    def can_split(self):
        """Check if the player can split their hand."""
        return (len(self.hands[0]) == 2 and 
                self.hands[0][0].rank == self.hands[0][1].rank)

    def split(self, deck):
        """Split the initial hand into two separate hands."""
        if not self.can_split():
            return False

        # Create a second hand with one card from the original hand
        second_hand = [self.hands[0].pop()]
        self.hands.append(second_hand)

        # Draw a new card for each hand
        self.hands[0].append(deck.deal_card())
        self.hands[1].append(deck.deal_card())

        return True

    async def async_init(self, ctx):
        self.balance = await bank.get_balance(ctx.author)
        print(f"Initialized player {self.name} with balance {self.balance}")

    def __str__(self):
        """Return a string representing the player's hand."""
        return f"{self.name}'s hand: " + ", ".join(str(card) for card in self.hand)

    def __repr__(self):
        """Return an 'official' representation of the player's hand."""
        hand_repr = ", ".join(repr(card) for card in self.hand)
        return f"Player('{self.name}', hand=[{hand_repr}])"

    def place_bet(self, amount, available_balance):
        if amount > available_balance:
            return False  
        self.bet = amount
        return True

    async def clear_hand(self):
        await super().clear_hand()  # Call parent's clear_hand first
        self.hands = [self.hand]    # Reset hands list to contain only the cleared main hand
        self.bet = 0                # Reset bet amount


class Dealer(Participant):
    def __init__(self):
        super().__init__()
        self.name = "Dealer"
        self.show_one_card = True
        self.stand_on_score = 17
        self.stand_on_soft_17 = True

    def reveal_cards(self):
        self.show_one_card = False

    def should_hit(self):
        """Determines if the dealer should hit."""
        if self.score < self.stand_on_score:
            return True
        if self.stand_on_soft_17 and self.score == 17:
            return any(card.rank == "ace" for card in self.hand)
        return False

class TableView(discord.ui.View):
    def __init__(self, game_state):
        super().__init__(timeout=None)
        self.game_state = game_state

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green, emoji="🪑")
    async def sit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_id = interaction.user.id
        
        # Check if player is already in game or queue
        if (player_id in self.game_state.player_objects or 
            player_id in self.game_state.join_queue):
            await interaction.response.send_message(
                "You are already in the game or waiting to join.",
                ephemeral=True
            )
            return

        # Add to join queue
        self.game_state.join_queue.append(player_id)
        await interaction.response.send_message(
            f"You will join the table at the start of the next round.",
            ephemeral=True
        )

    @discord.ui.button(label="Leave Game", style=discord.ButtonStyle.red, emoji="👋")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_id = interaction.user.id
        
        # Check if player is actually in game
        if (player_id not in self.game_state.player_objects or 
            player_id in self.game_state.leave_queue):
            await interaction.response.send_message(
                "You are not in the game or have already requested to leave.",
                ephemeral=True
            )
            return

        # Add to leave queue
        self.game_state.leave_queue.append(player_id)
        await interaction.response.send_message(
            f"You will leave the table at the end of this round.",
            ephemeral=True
        )

class GameState:
    def __init__(self, bot, channel_id, games, config):
        self.bot = bot
        self.config = config
        self.channel_id = channel_id
        self.games = games
        self.deck = None  # Will be initialized with guild config
        self.player_objects = {}
        self.dealer = Dealer()
        self.end_game = False
        self.state = "Stopped"
        self.join_queue = []
        self.leave_queue = []
        self.action_emojis = {
            "hit": "👊",
            "stand": "🛑",
            "double": "💰",
            "split": "✂️"
        }
        self.view = TableView(self)  # Add this line
        self.game_message = None
        self.face_down_card = "🂠"  # Unicode playing card back symbol
        self.current_big_blind = 0  # Index to track big blind position
        self.pot = 0

    async def initialize_from_guild_config(self, guild):
        """Initialize game settings from guild config"""
        guild_config = await self.config.guild(guild).all()
        
        # Initialize deck with guild config
        self.deck = Deck(num_decks=guild_config['num_decks'])
        
        # Set game settings from guild config
        self.min_bet = guild_config['min_bet']
        self.max_bet = guild_config['max_bet']
        self.bet_state_timeout = guild_config['bet_timeout']
        self.payouts = {
            "Win": guild_config['payouts']['win'],
            "Blackjack": guild_config['payouts']['blackjack']
        }
        self.blinds = guild_config['blinds']

    def has_active_players(self):
        """Check if there are any active players at the table."""
        return bool(self.player_objects)

    async def clear_states(self, ctx, channel_id):
        """Reset all game states for the next round"""
        for player in self.player_objects.values():
            await player.clear_hand()
        await self.dealer.clear_hand()
        self.end_game = False
        self.state = "Waiting for bets"
        if not hasattr(self, 'pot_carries_over'):
            self.pot = 0  # Reset pot only if it doesn't carry over
        self.pot_carries_over = False
        
    async def process_queues(self, ctx):
        """Process join and leave queues at the start of each round."""
        embed = self.game_message.embeds[0]
        
        # Handle leaves
        for player_id in self.leave_queue:
            if player_id in self.player_objects:
                del self.player_objects[player_id]
                member = ctx.guild.get_member(player_id)
                if member:
                    embed.description = f"👋 {member.mention} has left the game."
                    await self.game_message.edit(embed=embed)
                    await asyncio.sleep(1)

        self.leave_queue.clear()

        # Handle joins
        for player_id in self.join_queue:
            if player_id not in self.player_objects:
                member = ctx.guild.get_member(player_id)
                if member:
                    player = Player(member.display_name, ctx)
                    await player.async_init(ctx)
                    self.player_objects[player_id] = player
                    embed.description = f"✨ {member.mention} has joined the game."
                    await self.game_message.edit(embed=embed)
                    await asyncio.sleep(1)

        self.join_queue.clear()

    async def take_bets(self, ctx, channel_id):
        self.state = "Taking bets"
        for player_id, player in self.player_objects.items():
            member = ctx.guild.get_member(player_id)
            if not member:
                continue
                
            player_balance = await bank.get_balance(member)
            embed = self.game_message.embeds[0]
            embed.description = f"💰 {member.mention}'s turn to bet\nBalance: {player_balance}"
            await self.game_message.edit(embed=embed)

            betting_view = BettingView(self, player, self.min_bet, self.max_bet)
            bet_message = await ctx.send(
                f"{member.mention}'s betting turn\nCurrent bet: 0",
                view=betting_view
            )

            await betting_view.wait()
            try:
                await bet_message.delete()
            except discord.HTTPException:
                pass

    async def add_player(self, player_id, ctx):
        player = Player(self.bot.get_user(player_id).name, ctx)
        await player.async_init(ctx)
        self.player_objects[player_id] = player

    # The initial gameplay logic 
    async def setup_game(self, ctx, channel_id, embed):
        """Setup and deal initial cards."""
        self.state = "Dealing cards"
        game = self.games.get(channel_id)
        if game is None:
            embed.description = f"No game found for channel ID: {channel_id}"
            await self.game_message.edit(embed=embed)
            return
            
        if game.deck.num_cards_remaining() == 0:
            embed.description = "The shoe is empty! Reshuffling..."
            await self.game_message.edit(embed=embed)
            game.deck.refill()
            await asyncio.sleep(2)
        
        game.deck.shuffle()

        # Deal cards to players and dealer
        for player_id, player in game.player_objects.items():
            user = self.bot.get_user(player_id)
            if user is None:
                continue  
            player.draw_card(game.deck)
            player.draw_card(game.deck)
            player.calculate_score()

        dealer = game.dealer
        dealer.draw_card(game.deck)
        dealer.draw_card(game.deck)
        dealer.score = dealer.hand[0].value

        game.state = "In Progress"
        await self.card_table_update_embed(embed, game, reveal_dealer=False)
        await self.game_message.edit(embed=embed)

    async def reset_player_and_dealer_states(self):
        print(f"Clearing states for channel ID: {self.channel_id}")
        await self.dealer.clear_hand()  
        for player in self.player_objects.values():
            await player.clear_hand()

    async def player_turns(self, ctx, channel_id, embed):
        game = self.games[channel_id]
        game.state = "Player Turns"
        
        for player_id, player in list(game.player_objects.items()):
            user = self.bot.get_user(player_id)
            hand_index = 0
            
            while hand_index < len(player.hands):
                current_hand = player.hands[hand_index]
                player.current_hand_index = hand_index
                
                # Calculate initial score
                player.score = sum(card.value for card in current_hand)
                aces = sum(1 for card in current_hand if card.rank == "ace")
                while player.score > 21 and aces:
                    player.score -= 10
                    aces -= 1

                # Auto-complete if blackjack
                if player.score == 21:
                    await ctx.send(f"🎯 {user.mention} has Blackjack!")
                    hand_index += 1
                    continue

                # Main action loop
                while True:
                    if player.score > 21:  # Check for bust before showing actions
                        await ctx.send(f"{user.mention} busts with {player.score}!")
                        break
                        
                    action_view = PlayerActionView(game, player, current_hand)
                    action_message = await ctx.send(
                        f"{user.mention}'s turn - Score: {player.score}",
                        view=action_view
                    )

                    try:
                        await action_view.wait()
                        decision = action_view.action_taken

                        if decision is None:  # Timeout
                            await ctx.send(f"{user.mention} took too long - Standing automatically.")
                            break

                        if decision == "stand":
                            await ctx.send(f"{user.mention} stands on {player.score}.")
                            break

                        elif decision == "hit":
                            card = game.deck.deal_card()
                            current_hand.append(card)
                            # Recalculate score
                            player.score = sum(card.value for card in current_hand)
                            aces = sum(1 for card in current_hand if card.rank == "ace")
                            while player.score > 21 and aces:
                                player.score -= 10
                                aces -= 1
                            await self.card_table_update_embed(embed, game, reveal_dealer=False)
                            await game.game_message.edit(embed=embed)
                            continue  # Continue the loop for more actions

                        elif decision == "double":
                            await bank.withdraw_credits(ctx.guild.get_member(player_id), player.bet)
                            player.bet *= 2
                            card = game.deck.deal_card()
                            current_hand.append(card)
                            player.score = sum(card.value for card in current_hand)
                            aces = sum(1 for card in current_hand if card.rank == "ace")
                            while player.score > 21 and aces:
                                player.score -= 10
                                aces -= 1
                            await self.card_table_update_embed(embed, game, reveal_dealer=False)
                            await game.game_message.edit(embed=embed)
                            if player.score > 21:
                                await ctx.send(f"{user.mention} busts with {player.score}!")
                            else:
                                await ctx.send(f"{user.mention} doubled down to {player.score}")
                            break

                        elif decision == "split" and hand_index == 0:
                            await bank.withdraw_credits(ctx.guild.get_member(player_id), player.bet)
                            player.split(game.deck)
                            await ctx.send(f"{user.mention} splits their hand!")
                            await self.card_table_update_embed(embed, game, reveal_dealer=False)
                            await game.game_message.edit(embed=embed)
                            break

                    finally:
                        try:
                            await action_message.delete()
                        except discord.HTTPException:
                            pass

                hand_index += 1  # Move to next hand after current hand is complete

    async def card_table_update_embed(self, embed, game, reveal_dealer=True, status_message=""):
        embed.clear_fields()
        
        # Add visual game progress bar
        progress_markers = {
            "Taking bets": "💰 ⬜ ⬜ ⬜",
            "Dealing cards": "✅ 🎴 ⬜ ⬜",
            "Player Turns": "✅ ✅ 👤 ⬜",
            "Dealer turn": "✅ ✅ ✅ 🎲",
        }
        progress = progress_markers.get(game.state, "⬜ ⬜ ⬜ ⬜")
        embed.add_field(name="Game Progress", value=progress, inline=False)

        # Add status message with emoji indicators
        if status_message:
            embed.add_field(name="Status", value=status_message, inline=False)

        # Enhance player hand display
        for player_id, player in game.player_objects.items():
            user = self.bot.get_user(player_id)
            
            for hand_index, hand in enumerate(player.hands):
                hand_str = " ".join(str(card) for card in hand)  # This will now use the new Unicode card display
                score = sum(card.value for card in hand)
                
                # Add visual score indicator
                score_emoji = "🟢" if score <= 21 else "🔴"
                if score == 21:
                    score_emoji = "⭐"
                
                hand_name = f"{user.display_name}'s Hand {hand_index + 1}"
                value = (
                    f"{hand_str}\n"
                    f"{score_emoji} Score: {score}\n"
                    f"💵 Bet: {player.bet}"
                )
                embed.add_field(name=hand_name, value=value, inline=False)

        # Enhance dealer hand display
        dealer_value = ""
        if reveal_dealer:
            dealer_hand_str = " ".join(str(card) for card in game.dealer.hand)
            score_emoji = "🟢" if game.dealer.score <= 21 else "🔴"
            if game.dealer.score == 21:
                score_emoji = "⭐"
            dealer_value = f"{dealer_hand_str}\n{score_emoji} Score: {game.dealer.score}"
        else:
            face_up_card = str(game.dealer.hand[0])  # This will use the new Unicode display
            dealer_value = f"{face_up_card} {self.face_down_card}"
        
        embed.add_field(name="Dealer's Hand", value=dealer_value, inline=False)

        # Add game info with emojis
        embed.add_field(
            name="Game Info",
            value=(
                f"🎴 Cards in Shoe: {game.deck.num_cards_remaining()}\n"
                f"👥 Active Players: {len(game.player_objects)}\n"
                f"💰 Current Pot: {self.pot}"
            ),
            inline=False
        )
        await self.game_message.edit(embed=embed, view=self.view)  # Add view parameter

    async def dealer_turn(self, ctx, channel_id, embed):
        """Handle dealer's turn using single embed."""
        self.state = "Dealer turn"
        game = self.games[channel_id]
        dealer = game.dealer
        dealer.calculate_score()

        # Update embed with dealer's revealed hand
        await self.card_table_update_embed(embed, game, reveal_dealer=True)
        await self.game_message.edit(embed=embed)
        await asyncio.sleep(2)

        while dealer.score < 17:
            if game.deck.num_cards_remaining() == 0:
                embed.description = "The shoe is empty! Reshuffling..."
                await self.game_message.edit(embed=embed)
                game.deck.refill()
                await asyncio.sleep(2)
                
            dealer.draw_card(game.deck)
            dealer.calculate_score()
            
            await self.card_table_update_embed(embed, game, reveal_dealer=True)
            embed.description = f"Dealer draws... Current score: {dealer.score}"
            await self.game_message.edit(embed=embed)
            await asyncio.sleep(2)

        final_status = ""
        if dealer.score == 21:
            final_status = "🎯 Dealer hits 21!"
        elif dealer.score > 21:
            final_status = f"💥 Dealer busts with {dealer.score}!"
        else:
            final_status = f"🛑 Dealer stands on {dealer.score}"

        embed.description = final_status
        await self.game_message.edit(embed=embed)

    async def payout(self, ctx, channel_id):
        """Modified payout to include pot distribution and round summary"""
        game = self.games[channel_id]
        dealer = game.dealer
        embed = self.game_message.embeds[0]
        results = []
        winners = []
        summary_data = {
            "players": [],
            "total_pot": self.pot,
            "dealer_score": dealer.score,
            "dealer_busted": dealer.score > 21
        }

        # Determine winners and build summary data
        for player_id, player in game.player_objects.items():
            member = ctx.guild.get_member(player_id)
            if not member:
                continue

            player_summary = {
                "name": member.display_name,
                "hands": [],
                "total_won": 0,
                "total_bet": player.bet
            }

            for hand_index, hand in enumerate(player.hands):
                hand_score = sum(card.value for card in hand)
                aces = sum(1 for card in hand if card.rank == "ace")
                while hand_score > 21 and aces:
                    hand_score -= 10
                    aces -= 1

                hand_result = {
                    "cards": " ".join(str(card) for card in hand),
                    "score": hand_score,
                    "busted": hand_score > 21,
                    "blackjack": hand_score == 21 and len(hand) == 2,
                    "won": False
                }

                if hand_score <= 21 and (dealer.score > 21 or hand_score > dealer.score):
                    winners.append((member, player, hand_score))
                    hand_result["won"] = True
                
                player_summary["hands"].append(hand_result)
            
            summary_data["players"].append(player_summary)

        # Calculate payouts and update summary
        if winners:
            pot_share = self.pot / len(winners)
            for member, player, score in winners:
                win_amount = round(player.bet * self.payouts["Win"] + pot_share)
                await bank.deposit_credits(member, win_amount)
                
                # Update player summary with winnings
                for p in summary_data["players"]:
                    if p["name"] == member.display_name:
                        p["total_won"] = win_amount
                        break

        # Create formatted round summary embed
        embed.clear_fields()
        embed.title = "🎲 Round Summary"
        
        # Dealer's final hand
        dealer_status = "💥 BUSTED!" if dealer.score > 21 else "🎯 21!" if dealer.score == 21 else f"📍 {dealer.score}"
        dealer_cards = " ".join(str(card) for card in dealer.hand)
        embed.add_field(
            name="Dealer's Final Hand",
            value=f"{dealer_cards}\n{dealer_status}",
            inline=False
        )

        # Player results
        for player in summary_data["players"]:
            result_lines = []
            for i, hand in enumerate(player["hands"]):
                hand_num = f" (Hand {i+1})" if len(player["hands"]) > 1 else ""
                status = "💥 BUST!" if hand["busted"] else "⭐ BLACKJACK!" if hand["blackjack"] else "✅ WIN!" if hand["won"] else "❌ LOSS"
                result_lines.append(f"{hand['cards']} → {hand['score']} {status}")
            
            profit_loss = player["total_won"] - player["total_bet"]
            chips_status = f"🔼 +{profit_loss}" if profit_loss > 0 else f"🔽 {profit_loss}"
            
            embed.add_field(
                name=f"{player['name']}'s Results",
                value="\n".join(result_lines) + f"\nChips: {chips_status}",
                inline=False
            )

        # Pot summary
        if winners:
            embed.add_field(
                name="💰 Pot Distribution",
                value=f"Total Pot: {self.pot}\nSplit between {len(winners)} winner(s)",
                inline=False
            )
        else:
            embed.add_field(
                name="💰 Pot Status",
                value=f"Pot ({self.pot} chips) carries to next round",
                inline=False
            )

        await self.game_message.edit(embed=embed)
        await asyncio.sleep(5)  # Give players time to read the summary

    async def build_game_state_embed(self, game):
        embed = discord.Embed(title="RealBlackjack", color=0xFF69B4, description="Game Table")
        embed.set_author(name="Blackjack Dealer", icon_url="")

        # Update the embed with the current hands and scores
        await self.update_embed_with_hands(embed, game)

        
        embed.add_field(
            name="Cards Left in Shoe", value=str(len(game.deck.cards)), inline=False
        )

    
        return embed

    async def check_and_end_game(self, ctx, channel_id):
        """Check if there are active players; if none, end the game."""
        if not self.has_active_players():
            await ctx.send("No players remaining at the table. Ending the game.")
            self.state = "Stopped"
            del self.games[channel_id]

    async def collect_blinds(self, ctx):
        """Collect small and big blinds from players"""
        if len(self.player_objects) < 2:
            return False
            
        embed = self.game_message.embeds[0]
        player_ids = list(self.player_objects.keys())
        
        # Calculate positions
        big_blind_pos = self.current_big_blind % len(player_ids)
        small_blind_pos = (big_blind_pos - 1) % len(player_ids)
        
        # Get players in blind positions
        big_blind_player = self.player_objects[player_ids[big_blind_pos]]
        small_blind_player = self.player_objects[player_ids[small_blind_pos]]
        
        # Get guild members
        big_blind_member = ctx.guild.get_member(player_ids[big_blind_pos])
        small_blind_member = ctx.guild.get_member(player_ids[small_blind_pos])
        
        # Collect small blind
        small_blind_balance = await bank.get_balance(small_blind_member)
        if small_blind_balance >= self.blinds["small"]:
            await bank.withdraw_credits(small_blind_member, self.blinds["small"])
            self.pot += self.blinds["small"]
            embed.description = f"💰 {small_blind_member.mention} posts small blind: {self.blinds['small']}"
            await self.game_message.edit(embed=embed)
            await asyncio.sleep(1)
        else:
            embed.description = f"❌ {small_blind_member.mention} cannot afford small blind, removed from game"
            await self.game_message.edit(embed=embed)
            del self.player_objects[player_ids[small_blind_pos]]
            return False
            
        # Collect big blind
        big_blind_balance = await bank.get_balance(big_blind_member)
        if big_blind_balance >= self.blinds["big"]:
            await bank.withdraw_credits(big_blind_member, self.blinds["big"])
            self.pot += self.blinds["big"]
            embed.description = f"💰 {big_blind_member.mention} posts big blind: {self.blinds['big']}"
            await self.game_message.edit(embed=embed)
            await asyncio.sleep(1)
        else:
            embed.description = f"❌ {big_blind_member.mention} cannot afford big blind, removed from game"
            await self.game_message.edit(embed=embed)
            del self.player_objects[player_ids[big_blind_pos]]
            return False
            
        # Rotate blinds for next round
        self.current_big_blind = (self.current_big_blind + 1) % len(player_ids)
        return True

class RealBlackJack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}
        self.config = Config.get_conf(self, identifier=123452212232144515623667890)
        
        # Add guild defaults
        default_guild = {
            "min_bet": 10,
            "max_bet": 10000,
            "num_decks": 2,
            "join_timeout": 20,
            "bet_timeout": 15,
            "payouts": {
                "win": 2,
                "blackjack": 2.5
            },
            "blinds": {
                "big": 200,
                "small": 100
            },
            "max_players": 6
        }
        
        default_member = {
            "games_won": 0,
            "games_lost": 0,
            "total_chips_won": 0,
            "total_chips_lost": 0,
        }
        
        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)
        

    async def initialize_game_state(self, ctx, channel_id):
        """Initialize a new game state with guild-specific settings."""
        guild_config = await self.config.guild(ctx.guild).all()
        
        game_state = GameState(self.bot, channel_id, self.games, self.config)
        game_state.min_bet = guild_config["min_bet"]
        game_state.max_bet = guild_config["max_bet"]
        game_state.bet_state_timeout = guild_config["bet_timeout"]
        game_state.join_timeout = guild_config["join_timeout"]
        game_state.deck = Deck(num_decks=guild_config["num_decks"])
        game_state.payouts = {
            "Win": guild_config["payouts"]["win"],
            "Blackjack": guild_config["payouts"]["blackjack"]
        }
        game_state.blinds = guild_config["blinds"]
        
        return game_state

    async def update_wins(self, member):
        current_wins = await self.config.member(member).wins()
        await self.config.member(member).wins.set(current_wins + 1)
        self.logger.debug(f"Updated wins for {member.display_name}")

    async def update_losses(self, member):
        current_losses = await self.config.member(member).losses()
        await self.config.member(member).losses.set(current_losses + 1)
        # self.logger.debug(f"Updated losses for {member.display_name}")

    @commands.group()
    async def realblackjack(self, ctx):
        """Commands Group for Real Blackjack."""
        if ctx.guild is None: 
            await ctx.send("This command can only be used in a server.")
            return
        if ctx.invoked_subcommand is None:
            # Instead of showing error message, invoke help command
            pass
            
    @realblackjack.command()
    async def start(self, ctx):
        """ Start a game of Real Blackjack."""
        channel_id = ctx.channel.id
        if channel_id in self.games:
            await ctx.send("A game is already started in this channel.")
            return

        # Get guild-specific timeout
        join_timeout = await self.config.guild(ctx.guild).join_timeout()
        
        # Initialize joined players with the starter
        joined_players = [ctx.author.id]
        await ctx.send(f"{ctx.author.mention} starts a new game!\nGame will start in {join_timeout} seconds. Type join to sit at the table!")
        await ctx.send(f"{ctx.author.mention} has joined the game!")

        def check_join(msg):
            return (
                msg.content.lower() == "bj join" or msg.content.lower() == "join" and 
                msg.channel == ctx.channel and
                msg.author.id != ctx.author.id  # Don't let starter join again
            )

        while True:
            try:
                msg = await self.bot.wait_for(
                    "message", timeout=join_timeout, check=check_join
                )
                player_id = msg.author.id
                if player_id not in joined_players:
                    joined_players.append(player_id)
                    await ctx.send(f"{msg.author.mention} has joined the game!")
            except asyncio.TimeoutError:
                break

        if not joined_players:
            await ctx.send("No one joined. Game cancelled.")
            return

        # Create a dictionary of player objects
        player_dict = {
            player_id: Player(self.bot.get_user(player_id).name, ctx)
            for player_id in joined_players
        }

        # Initialize GameState with the players who have joined
        self.games[channel_id] = await self.initialize_game_state(ctx, channel_id)
        game = self.games[channel_id]
        game.player_objects = player_dict  # Set players directly
        embed = discord.Embed(title="Real Blackjack", color=0xFF69B4)

        for player in player_dict.values():
            await player.async_init(ctx)

        await ctx.send(f"Game starting! Use the buttons below to join or leave the table.")
        await self.play_game(ctx, channel_id, embed)


    @commands.group()
    @commands.is_owner()
    async def realblackjackset(self, ctx):
        """Admin Commands Group for Real Blackjack."""
        if ctx.guild is None: 
            await ctx.send("This command can only be used in a server.")
            return
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid blackjack command passed...")
            
    @realblackjackset.command()
    async def gamestate(self, ctx):
        """Show the current game state."""
        channel_id = ctx.channel.id
        if channel_id in self.games:
            game = self.games[channel_id]
            await ctx.send(f"Game state: {game.state}")
            
 
    @realblackjackset.command(name="endgame")
    @commands.is_owner()
    async def end(self, ctx):
        """End the game manually."""
        channel_id = ctx.channel.id
        if channel_id in self.games:
            del self.games[channel_id]
            await ctx.send("The game has ended.")
        else:
            await ctx.send("No game is currently running in this channel.")

    @realblackjackset.command(name="timeout")
    async def join_timeout(self, ctx, timeout: int):
        """Set the timeout for players to join the game."""
        if timeout < 10:
            await ctx.send("Timeout must be at least 10 seconds.")
            return
        if timeout > 30:
            await ctx.send("Timeout cannot be more than 30 seconds.")
            return
        self.join_state_timeout = timeout
        await ctx.send(f"Join timeout set to {timeout} seconds.")

    @realblackjackset.command(name="cardsleft")
    async def cards_remaining(self, ctx):
        """Returns how many cards are left in the shoe."""
        channel_id = ctx.channel.id
        game = self.games.get(channel_id)
        if not game:
            await ctx.send("There's no active game in this channel.")
            return
        if ctx.channel.id in game:
            remaining_cards = game.deck.num_cards_remaining()
            await ctx.send(f'There is an active game in this channel with {remaining_cards} cards left in the shoe.')
        else:
            await ctx.send("There's no active game in this channel.")

    @realblackjackset.command(name="settings")
    async def settings(self, ctx):
        """Display settings information and help for Real Blackjack admin commands."""
        # Get guild settings from config
        guild_settings = await self.config.guild(ctx.guild).all()
        game = self.games.get(ctx.channel.id)

        embed = discord.Embed(
            title="Real Blackjack Settings",
            color=0xFF69B4,
            description="Current game settings and admin commands"
        )
        embed.set_image(url="https://i.ibb.co/vXNSX8g/realblackjack-logo-transparent.png")

        # Add about field
        embed.add_field(
            name="About",
            value="Real Blackjack - A fully featured multiplayer blackjack game for Discord\nCreated by Slurms Mackenzie/ropeadope62",
            inline=False
        )

        # Add repository field
        embed.add_field(
            name="Repo",
            value="https://github.com/ropeadope62/discordcogs",
            inline=False
        )

        # Current settings using guild config values
        settings = [
            ("Join Timeout", f"{guild_settings['join_timeout']} seconds"),
            ('Bet Timeout', f"{guild_settings['bet_timeout']} seconds"),
            ("Minimum Bet", f"{guild_settings['min_bet']} chips"),
            ("Maximum Bet", f"{guild_settings['max_bet']} chips"),
            ("Win Payout", f"{guild_settings['payouts']['win']}x"),
            ("Blackjack Payout", f"{guild_settings['payouts']['blackjack']}x"),
            ("Blinds", f"Big: {guild_settings['blinds']['big']} / Small: {guild_settings['blinds']['small']}"),
            ("Number of Decks", f"{guild_settings['num_decks']} decks"),
            ("Max Players", f"{guild_settings['max_players']}")
        ]

        settings_text = "\n".join(f"**{name}:** {value}" for name, value in settings)
        embed.add_field(
            name="Current Settings",
            value=settings_text,
            inline=False
        )

        # Admin commands
        # ...existing admin commands code...

        await ctx.send(embed=embed)

    @realblackjackset.command(name="bettinglimits")
    @commands.admin_or_permissions(administrator=True)
    async def betting_limits(self, ctx, min_bet: int, max_bet: int):
        """Set the minimum and maximum betting amounts for this server."""
        if min_bet < 1 or max_bet < min_bet:
            await ctx.send("Invalid betting limits. Minimum bet must be at least 1 and maximum bet must be greater than minimum.")
            return
            
        await self.config.guild(ctx.guild).min_bet.set(min_bet)
        await self.config.guild(ctx.guild).max_bet.set(max_bet)
        
        # Update any active game in this guild
        if ctx.channel.id in self.games:
            game = self.games[ctx.channel.id]
            game.min_bet = min_bet
            game.max_bet = max_bet
            
        await ctx.send(f"Betting limits updated: Min: {min_bet}, Max: {max_bet}")

    @realblackjackset.command(name="payouts")
    @commands.admin_or_permissions(administrator=True)
    async def set_payouts(self, ctx, win_multiplier: float, blackjack_multiplier: float):
        """Set the payout multipliers for wins and blackjacks."""
        if win_multiplier < 1 or blackjack_multiplier < 1:
            await ctx.send("Multipliers must be greater than 1.")
            return
            
        async with self.config.guild(ctx.guild).payouts() as payouts:
            payouts["win"] = win_multiplier
            payouts["blackjack"] = blackjack_multiplier
            
        await ctx.send(f"Payout multipliers updated: Win: {win_multiplier}x, Blackjack: {blackjack_multiplier}x")

    @realblackjackset.command(name="decks")
    @commands.admin_or_permissions(administrator=True)
    async def set_decks(self, ctx, number: int):
        """Set the number of decks used in the shoe."""
        if number < 1 or number > 8:
            await ctx.send("Number of decks must be between 1 and 8.")
            return
            
        await self.config.guild(ctx.guild).num_decks.set(number)
        await ctx.send(f"Number of decks set to {number}")

    @realblackjackset.command(name="timeouts")
    @commands.admin_or_permissions(administrator=True)
    async def set_timeouts(self, ctx, join_timeout: int, bet_timeout: int):
        """Set the join and bet timeouts for the game."""
        if join_timeout < 10 or bet_timeout < 10:
            await ctx.send("Timeouts must be at least 10 seconds.")
            return
            
        if join_timeout > 60 or bet_timeout > 60:
            await ctx.send("Timeouts cannot exceed 60 seconds.")
            return
            
        await self.config.guild(ctx.guild).join_timeout.set(join_timeout)
        await self.config.guild(ctx.guild).bet_timeout.set(bet_timeout)
        await ctx.send(f"Join timeout set to {join_timeout} seconds, Bet timeout set to {bet_timeout} seconds")

    async def place_bet(self, ctx, player_id, amount):
        user = self.bot.get_user(player_id)
        if user is None:
            return False

        # Retrieve the balance of the user
        balance = await bank.get_balance(user)

        player = self.player_objects.get(player_id)
        if player is None:
            return False

        success = player.place_bet(amount, balance)
        if not success:
            await ctx.send(
                f"You don't have enough chips to place that bet. Your balance is {balance}."
            )
        return success

    async def play_game(self, ctx, channel_id, embed):
        game = self.games[channel_id]
        game.end_game = False

        while not game.end_game:
            # Create new round embed
            round_embed = discord.Embed(
                title="Real Blackjack",
                color=0xFF69B4,
                description="🃏 Starting New Round..."
            )
            round_embed.set_thumbnail(url="https://i.ibb.co/7vJ2Y2V/realblackjack-logo-transparent.png")
            game.game_message = await ctx.send(embed=round_embed, view=game.view)

            # Process join and leave queues
            round_embed.description = "👥 Processing player changes..."
            await game.game_message.edit(embed=round_embed)
            await game.process_queues(ctx)

            if not game.has_active_players():
                round_embed.description = "No players remaining. Ending the game."
                await game.game_message.edit(embed=round_embed)
                game.end_game = True
                del self.games[channel_id]
                return

            # Collect blinds
            if not await game.collect_blinds(ctx):
                if not game.has_active_players():
                    round_embed.description = "Game ended due to insufficient players for blinds."
                    await game.game_message.edit(embed=round_embed)
                    game.end_game = True
                    del self.games[channel_id]
                    return

            # Take bets and play a round
            round_embed.description = "💰 Taking Bets..."
            await game.game_message.edit(embed=round_embed)
            await game.take_bets(ctx, channel_id)

            if game.end_game:
                round_embed.description = "Game manually stopped. Ending the game."
                await game.game_message.edit(embed=round_embed)
                del self.games[channel_id]
                return

            # Setup the game and deal initial cards
            round_embed.description = "🎴 Dealing Cards..."
            await game.game_message.edit(embed=round_embed)
            await game.setup_game(ctx, channel_id, round_embed)

            # Player turns
            for player_id, player in game.player_objects.items():
                user = self.bot.get_user(player_id)
                round_embed.description = f"🎮 {user.display_name}'s Turn..."
                await game.game_message.edit(embed=round_embed)
                await game.player_turns(ctx, channel_id, round_embed)

            # Dealer turn and payouts
            if any(player.score <= 21 for player in game.player_objects.values()):
                round_embed.description = "🎰 Dealer's Turn..."
                await game.game_message.edit(embed=round_embed)
                await game.dealer_turn(ctx, channel_id, round_embed)

            # Payout results
            round_embed.description = "💵 Calculating Payouts..."
            await game.game_message.edit(embed=round_embed)
            await game.payout(ctx, channel_id)

            # Clear game states for the next round
            await game.clear_states(ctx, channel_id)

            if game.end_game:
                round_embed.description = "Game manually stopped. Ending the game."
                await game.game_message.edit(embed=round_embed)
                del self.games[channel_id]
                return

            # Brief delay before next round without changing the embed
            await ctx.send("🔄 Next round starts in 10 seconds.\nUse the buttons below to join or leave the table.")
            await asyncio.sleep(10)

            # Delete previous round's embed to keep chat cleaner
            try:
                await game.game_message.delete()
            except discord.HTTPException:
                pass

        if channel_id in self.games:
            del self.games[channel_id]
            
        await ctx.send("Game over. Thanks for playing!")


class BettingView(discord.ui.View):
    def __init__(self, game_state, player, min_bet, max_bet):
        super().__init__(timeout=30)
        self.game_state = game_state
        self.player = player
        self.min_bet = min_bet
        self.max_bet = max_bet
        self.current_bet = 0

    @discord.ui.button(label="10", style=discord.ButtonStyle.secondary, emoji="💰")
    async def bet_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_to_bet(interaction, 10)

    @discord.ui.button(label="50", style=discord.ButtonStyle.secondary, emoji="💰")
    async def bet_50(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_to_bet(interaction, 50)

    @discord.ui.button(label="100", style=discord.ButtonStyle.secondary, emoji="💰")
    async def bet_100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_to_bet(interaction, 100)

    @discord.ui.button(label="500", style=discord.ButtonStyle.secondary, emoji="💰")
    async def bet_500(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_to_bet(interaction, 500)

    @discord.ui.button(label="1000", style=discord.ButtonStyle.secondary, emoji="💰")
    async def bet_1000(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_to_bet(interaction, 1000)

    @discord.ui.button(label="Clear", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def clear_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_bet = 0
        await interaction.response.edit_message(content=f"Current bet: {self.current_bet}")

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def confirm_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_bet < self.min_bet:
            await interaction.response.send_message(f"Minimum bet is {self.min_bet}", ephemeral=True)
            return
        
        member = interaction.user
        balance = await bank.get_balance(member)
        if self.current_bet > balance:
            await interaction.response.send_message("You don't have enough chips!", ephemeral=True)
            return
            
        self.player.bet = self.current_bet
        await bank.withdraw_credits(member, self.current_bet)
        self.stop()
        await interaction.message.delete()

    async def add_to_bet(self, interaction: discord.Interaction, amount):
        if interaction.user.id != list(self.game_state.player_objects.keys())[0]:
            await interaction.response.send_message("It's not your turn to bet!", ephemeral=True)
            return
            
        new_bet = self.current_bet + amount
        if new_bet > self.max_bet:
            await interaction.response.send_message(f"Maximum bet is {self.max_bet}", ephemeral=True)
            return
            
        self.current_bet = new_bet
        await interaction.response.edit_message(content=f"Current bet: {self.current_bet}")


class PlayerActionView(discord.ui.View):
    def __init__(self, game_state, player, current_hand):
        super().__init__(timeout=30)
        self.game_state = game_state
        self.player = player
        self.current_hand = current_hand
        self.action_taken = None
        
        # Disable split button if not eligible
        if not (len(current_hand) == 2 and current_hand[0].rank == current_hand[1].rank):
            self.split_button.disabled = True
            
        # Disable double button if not enough balance or not first action
        if len(current_hand) != 2:
            self.double_button.disabled = True

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="👊")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != list(self.game_state.player_objects.keys())[0]:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        await interaction.response.defer()
        self.action_taken = "hit"
        self.stop()

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="🛑")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != list(self.game_state.player_objects.keys())[0]:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        await interaction.response.defer()
        self.action_taken = "stand"
        self.stop()

    @discord.ui.button(label="Double", style=discord.ButtonStyle.success, emoji="💰")
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != list(self.game_state.player_objects.keys())[0]:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        
        member = interaction.user
        player_balance = await bank.get_balance(member)
        
        if self.player.bet * 2 > player_balance:
            await interaction.response.send_message("Not enough chips to double down!", ephemeral=True)
            return
            
        await interaction.response.defer()
        self.action_taken = "double"
        self.stop()

    @discord.ui.button(label="Split", style=discord.ButtonStyle.primary, emoji="✂️")
    async def split_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != list(self.game_state.player_objects.keys())[0]:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
            
        member = interaction.user
        player_balance = await bank.get_balance(member)
        
        if self.player.bet * 2 > player_balance:
            await interaction.response.send_message("Not enough chips to split!", ephemeral=True)
            return
            
        await interaction.response.defer()
        self.action_taken = "split"
        self.stop()

async def setup(bot):
    await bot.add_cog(RealBlackJack(bot))