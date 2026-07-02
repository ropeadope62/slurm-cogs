![Bullshido](./bullshido.png)

# Bullshido

Bullshido is a hybrid Red-DiscordBot fighting cog built around exaggerated martial arts spectacle. Players pick a style, build a fighter over time, train and diet daily, fight other members, collect injuries, climb rankings, and optionally wager currency through Red's bank system.

## Requirements

- Red-DiscordBot with hybrid command support
- Red bank enabled for challenge wagers and injury treatment costs
- `OPENAI_API_KEY` only if you want the standalone `/bullshido hype` command

Live fights do not require OpenAI. Fight intros fall back to non-AI narration if AI generation is unavailable or fails.

## Feature Summary

- Interactive fighting style selection
- Simulated fights with rounds, live updates, decision scoring, KO, and TKO
- Style-based strike pools and weighted damage calculations
- Daily training and nutrition progression
- Automatic stat decay when training or diet is skipped
- XP, levels, and spendable stat points
- Persistent stamina between fights
- Permanent injury tracking and treatment
- Rankings, fight history, and detailed player stat views
- Optional wagered fights through Red bank integration
- Owner-tunable combat settings

## Fighting Styles

- Karate
- Muay-Thai
- Aikido
- Boxing
- Kung-Fu
- Judo
- Taekwondo
- Wrestling
- Krav-Maga
- Capoeira
- Sambo
- Kickboxing
- MMA
- Brazilian Jiu-Jitsu
- Zui Quan

## Player Commands

- `/bullshido help`
  - Shows the in-bot gameplay overview.

- `/bullshido setstyle`
  - Opens the fighting style selection UI.
  - Changing style resets your training level to `0`.

- `/bullshido list_fighting_styles`
  - Lists all available fighting styles.

- `/bullshido train`
  - Requires a selected fighting style.
  - Can be used once every 24 hours.
  - Increases training level by `10`, up to `100`.

- `/bullshido diet`
  - Requires a selected fighting style.
  - Can be used once every 24 hours.
  - Increases nutrition level by `10`, up to `100`.

- `/bullshido distribute_points`
  - Opens the stat allocation UI if you have unspent level points.
  - Spend points on health, stamina, or damage bonuses.

- `/bullshido fight @opponent`
  - Starts a normal fight.
  - Both fighters must have a selected style.
  - Both fighters must have enough stamina to begin.
  - You cannot fight yourself.

- `/bullshido challenge @opponent <bet>`
  - Starts a wagered fight using Red bank currency.
  - Both fighters must be able to afford the wager.
  - The opponent must answer `yes` or `no` in the same channel within 30 seconds.
  - Draws refund both fighters.

- `/bullshido hype @fighter1 @fighter2 [wager] [challenge]`
  - Generates a standalone hype embed.
  - Requires `OPENAI_API_KEY`.

- `/bullshido player_stats [@user]`
  - Shows detailed fighter stats for yourself or another member.
  - Alias: `stats`

- `/bullshido fight_record`
  - Shows your last 10 recorded fights.

- `/bullshido rankings`
  - Shows the top 25 fighters by win/loss ratio.
  - Aliases: `rank`, `leaderboard`, `lb`

- `/bullshido top_injuries`
  - Shows the 10 fighters with the most permanent injuries.

- `/bullshido injuries [@user]`
  - Shows permanent injuries for yourself or another member.
  - Aliases: `injury`, `inj`

- `/bullshido treat <injury>`
  - Treats one of your permanent injuries.
  - Treatment cost depends on the injury.
  - If socialized medicine is enabled, the configured payer covers the bill.

## Owner Commands

### Settings

- `/bullshidoset`
  - Displays the current Bullshido guild settings.

- `/bullshidoset socializedmedicine [@user]`
  - Toggles socialized medicine.
  - When enabling it, you must specify the member who will pay treatment costs.

- `/bullshidoset rounds <int>`
  - Sets the number of rounds in each fight.

- `/bullshidoset max_strikes_per_round <int>`
  - Sets the maximum number of strikes per player per round.

- `/bullshidoset training_weight <float>`
  - Sets how much training contributes to damage.

- `/bullshidoset diet_weight <float>`
  - Sets how much nutrition contributes to damage.

- `/bullshidoset damage_bonus_weight <float>`
  - Sets how strongly damage bonus contributes to damage.

- `/bullshidoset base_health <int>`
  - Sets base fighter health before bonuses.

- `/bullshidoset action_cost <int>`
  - Sets the configured action cost value.

- `/bullshidoset base_miss_probability <float>`
  - Sets the base miss chance before modifiers.

- `/bullshidoset base_stamina_cost <int>`
  - Sets the base stamina cost before modifiers.

- `/bullshidoset critical_chance <float>`
  - Sets the base critical hit chance.

- `/bullshidoset permanent_injury_chance <float>`
  - Sets the chance that a critical injury becomes permanent.

### Progression And Maintenance

- `/bullshidoset set_level @user <level>`
  - Sets a player's level and updates available level-up points.

- `/bullshidoset reset_level @user`
  - Resets a player's level, XP, and bonus stats.

- `/bullshidoset set_player_stats @user <stamina_bonus> <health_bonus> <damage_bonus>`
  - Directly sets a player's bonus stats.

- `/bullshido reset_stats`
  - Confirms and resets stored user data fields to defaults.

- `/bullshido reset_config`
  - Clears all stored Bullshido user data.

- `/bullshido clear_old_config`
  - Clears stored user data for cleanup or migration recovery.

### Debug And Testing

- `/bullshido log`
  - Shows the in-memory Bullshido log.

- `/bullshido test_fight_image @player1 @player2`
  - Generates a sample fight image for testing.

## Tracked Fighter Stats

Bullshido stores and surfaces these fighter attributes:

- fighting style
- wins by result type
- losses by result type
- draws
- XP
- level
- unspent level points
- stamina bonus
- health bonus
- damage bonus
- training level
- nutrition level
- morale
- intimidation level
- initiative
- stored stamina
- prize money won
- prize money lost
- permanent injuries
- fight history

## Progression Rules

### XP And Levels

- Decisive fights award XP to both fighters.
- Level-ups grant points you can spend through `/bullshido distribute_points`.
- Stat spending currently supports health, stamina, and damage bonuses.

### Daily Training And Diet

- Training and diet are separate once-per-day actions.
- Each successful use adds `10` points to that track.
- Training and nutrition both cap at `100`.
- A background task checks inactivity hourly.
- For each full missed day, the skipped track loses `10` points down to a minimum of `1`.

### Initiative

- Initiative is based on recent server activity over the last 15 minutes.
- More recent chat activity increases initiative up to `100`.
- Initiative and training together influence who attacks first.

## Fight Mechanics

### Start Conditions

- Both fighters must be different users.
- Both fighters must have a selected style.
- Both fighters must have enough stamina to start.
- Only one fight can run in a channel at a time.

### Health And Stamina

- Total health is calculated as `base_health + health_bonus * 10`.
- Displayed stamina is calculated as `stamina_level + stamina_bonus * 5`.
- Stamina is preserved between fights and partially recovers after a match.
- Strike stamina cost is affected by training, nutrition, intimidation, and grapple-style moves.

### Damage, Miss Chance, And Critical Hits

- Each style has its own strike pool and damage ranges.
- Adjusted damage uses:
  - training level
  - nutrition level
  - damage bonus
  - configured damage weights
- A random post-adjustment damage modifier is applied to each strike.
- Miss chance is affected by:
  - base miss probability
  - attacker stamina
  - defender stamina
  - training difference
  - intimidation difference
- Critical hit chance is affected by:
  - base critical chance
  - training difference
  - intimidation difference

### Injuries

- Critical hits can cause injuries.
- Permanent injuries can occur based on the configured permanent injury chance.
- Hitting an already permanently injured body part deals double damage.
- Permanent injuries can be treated later with `/bullshido treat`.

### End States And Scoring

- Fights can end by KO, TKO, decision, or draw.
- If neither fighter is stopped early, the match goes to judges.
- Round scoring uses a 10-point-must style decision system.
- Rankings are based on win/loss ratio rather than XP.

### Morale And Intimidation

- Intimidation is recalculated from KO and TKO wins and losses.
- Morale is tracked and updated after decisive results.
- Intimidation directly affects miss chance and finish pressure.

## AI Hype Behavior

- Live fights attempt to generate AI hype when available.
- If live hype generation fails, Bullshido falls back to a standard intro instead of cancelling the fight.
- The standalone `/bullshido hype` command still requires `OPENAI_API_KEY`.

## Notes

- Bullshido uses hybrid commands, so prefix and slash behavior depends on your Red setup.
- Wagered fights and injury treatment require Red bank integration.
- The owner maintenance commands can wipe stored fighter data.
