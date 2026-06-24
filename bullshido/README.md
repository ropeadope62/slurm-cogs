
![Bullshido](./bullshido.png)
# Bullshido - A Multiplayer Fighting Game for Discord

## Overview:

Bullshido is a Discord-based fighting game where players select a martial art style and engage in combat against each other. The game incorporates elements of randomness and strategy, making each fight unique and exciting, and a levelling system that allows players to improve their skills over time. Players can track their wins, losses, and other stats to monitor their progress and compare themselves to other players. Bullshido aims to provide an engaging and competitive experience for Discord users who enjoy martial arts and combat games. This cog rewards players for daily server interactions by performing their training and diet activities daily or else they will suffer stat penalties after 48 hours. 

## Features:

1. **Select Fighting Style**: Players can choose from a variety of fighting styles, each with unique strikes and damage ranges.
2. **Combat System**: Players take turns attacking each other, with the damage dealt being influenced by random modifiers for added unpredictability.
3. **Levelling System**: Through training, nutrition, and other attributes, players can increase their stats to improve their chances of winning fights.
4. **Player Stats**: Track wins, losses, and other stats to monitor progress and skill level.

## Commands:

1. `/bullshido info`
   - **Description**: Displays information about all available Bullshido game commands.
   - **Usage**: `/bullshido info`

> Optional AI hype support is available via `/bullshido hype` when `OPENAI_API_KEY` is configured in the environment.
   
2. `/bullshido setstyle`
   - **Description**: Allows a player to select their fighting style.
   - **Usage**: `/bullshido select_fighting_style`
   
3. `/bullshido list_fighting_styles`
   - **Description**: Lists all available fighting styles that players can choose from.
   - **Usage**: `/bullshido list_fighting_styles`
   
4. `/bullshido start_fight`
   - **Description**: Initiates a fight between two players.
   - **Usage**: `/bullshido start_fight <opponent>`
   - **Note**: Both players must have selected a fighting style before starting a fight.

5. `/bullshido player_stats`
   - **Description**: Displays the stats of a player, including wins, losses, and other attributes.
   - **Usage**: `/bullshido player_stats <player>`
   - **Note**: The player's name must be provided to view their stats.

6. `/bullshido ranking`
   - **Description**: Displays the ranking of players based on their wins and losses.
   - **Usage**: `/bullshido ranking`

7. `/bullshido injuries`
   - **Description**: Shows the permanent injuries sustained by a player.
   - **Usage**: `/bullshido injuries <player>`
   - **Note**: If a player name is not provided injuries will be displayed for the command user. 

8. `/bullshido treat`
   - **Description**: Allows a player to treat their permanent injuries.
   - **Usage**: `/bullshido treat <user> <injury>

## Gameplay:

### Choosing a Fighting Style:

Players use the `/bullshido select_fighting_style` command to choose their preferred fighting style from a list of martial arts, including Karate, Muay-Thai, Aikido, Boxing, Kung-Fu, Judo, Taekwondo, Wrestling, Sambo, MMA, Capoeira, Kick-Boxing, and Krav-Maga.

### Starting a Fight:

To challenge another player, use the `/bullshido start_fight <opponent>` command. Ensure both players have selected their fighting styles.

### Combat Mechanics:

1. The game determines which player goes first based on their training level. Players then take turns attacking each other.
2. Each attack deals a random amount of damage, influenced by the player

Bullshido - A Multiplayer Fighting Game for Discord
Overview:

The game determines which player goes first based on their training level. Players then take turns attacking each other.
Each attack deals a random amount of damage, influenced by the player’s chosen fighting style and stats, as well as the stats of the defender.
The combat actions are described in a humanized manner, e.g., "Player1 throws a punch into Player2's body causing 15 damage!"

Winning the Game:

The game continues for 3 rounds, with each player taking turns attacking and defending. Each round is scored separately. The player with the most points at the end of the 3 rounds wins the fight. Alternatively, a player can win by knocking out their opponent before the end of the 3 rounds. Knockouts can occur by TKO or KO. 


## Levelling System Explained

### Stamina Calculation

**Formula:**


`self.player1_stamina = self.player1_data.get('stamina_level', 100) + (self.player1_data.get('stamina_bonus', 0) * 5)
self.player2_stamina = self.player2_data.get('stamina_level', 100) + (self.player2_data.get('stamina_bonus', 0) * 5)` 

**Explanation:**

-   `stamina_level`: The base stamina level of the player, defaulting to 100.
-   `stamina_bonus`: Each point allocated to stamina increases it by a fixed amount (5 in this case).

**Impact:**

-   The total stamina for each player is the sum of their base stamina level and the bonus from their stamina stat points.
-   **Example:** If a player has a `stamina_level` of 100 and a `stamina_bonus` of 2, their total stamina would be `100 + (2 * 5) = 110`.

### Health Calculation

**Formula:**

`self.player1_health = 100 + (self.player1_data.get('health_bonus', 0) * 10)
self.player2_health = 100 + (self.player2_data.get('health_bonus', 0) * 10)` 

**Explanation:**

-   Each point allocated to health increases the player's health by a fixed amount (10 in this case).

**Impact:**

-   The total health for each player is the sum of a base health level (100) and the bonus from their health stat points.
-   **Example:** If a player has a `health_bonus` of 3, their total health would be `100 + (3 * 10) = 130`.

### Damage Calculation

**Formula:**

`def calculate_adjusted_damage(self, base_damage, training_level, diet_level, damage_bonus):
    training_bonus = math.log10(training_level + 1) * self.training_weight
    diet_bonus = math.log10(diet_level + 1) * self.diet_weight
    adjusted_damage = base_damage * (1 + training_bonus + diet_bonus + (damage_bonus * 0.05))
    return round(adjusted_damage)` 

**Explanation:**

-   `base_damage`: The base amount of damage dealt by a strike.
-   `training_bonus`: A multiplier based on the player's training level, contributing to the overall damage.
-   `diet_bonus`: A multiplier based on the player's diet level, contributing to the overall damage.
-   `damage_bonus`: Each point allocated to damage increases the base damage by a percentage (5% per point in this case).

**Impact:**

-   The total damage dealt by a player in a strike is influenced by their base damage, training level, diet level, and damage stat points.
-   **Example:** If a player's `base_damage` is 20, `training_level` is 2, `diet_level` is 3, and `damage_bonus` is 4:
    -   `training_bonus = math.log10(2 + 1) * 0.15 ≈ 0.071`
    -   `diet_bonus = math.log10(3 + 1) * 0.15 ≈ 0.09`
    -   `damage_bonus = 4 * 0.05 = 0.20`
    -   `adjusted_damage = 20 * (1 + 0.071 + 0.09 + 0.20) ≈ 20 * 1.361 = 27.22`
    -   The final damage would be `round(27.22) = 27`.

### Summary

1.  **Stamina**: The player's stamina determines how many actions they can perform before getting tired. Each point in stamina increases the total stamina by 5 units.
2.  **Health**: The player's health determines how much damage they can take before losing. Each point in health increases the total health by 10 units.
3.  **Damage**: The player's damage output in strikes is influenced by their training level, diet level, and damage points. Each point in damage increases the base damage by 5%.