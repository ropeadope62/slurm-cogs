import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

if load_dotenv:
    load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_AVAILABLE = bool(OPENAI_API_KEY and OpenAI is not None)

client = OpenAI(api_key=OPENAI_API_KEY) if AI_AVAILABLE else None


def _fallback_hype(attacker_name, defender_name, wager: int = 0):
    if wager:
        return (
            f"{attacker_name} and {defender_name} are set to clash with {wager} on the line. "
        )
    return (
        f"{attacker_name} and {defender_name} are set to clash in a Bullshido showdown. "
    )


def generate_hype(user_config, attacker_id, defender_id, attacker_name, defender_name):
    if not AI_AVAILABLE:
        return _fallback_hype(attacker_name, defender_name)

    # Define relevant keys
    relevant_keys = [
        "training_level",
        "nutrition_level",
        "wins",
        "losses",
        "fighting_style",
        "intimidation_level",
    ]

    # Initialize data dictionaries
    attacker_data = {}
    defender_data = {}

    # Check if fighters have fought before
    if "fight_history" in user_config[str(attacker_id)]:
        fighting_history = user_config[str(attacker_id)]["fight_history"]
        for fight in fighting_history:
            if fight["opponent"] == defender_name:
                # Extract relevant data for attacker and defender from the past fight
                attacker_data = {
                    key: fight.get(key) for key in relevant_keys if key in fight
                }
                defender_data = {
                    key: user_config[str(defender_id)].get(key) for key in relevant_keys
                }
                break

    # If no past fight data is found, use the general data
    if not attacker_data:
        attacker_data = {
            key: user_config[str(attacker_id)].get(key) for key in relevant_keys
        }
    if not defender_data:
        defender_data = {
            key: user_config[str(defender_id)].get(key) for key in relevant_keys
        }

    if not attacker_data or not defender_data:
        return "Invalid attacker or defender ID."

    # Summarize the data to reduce token usage
    attacker_summary = f"{attacker_name}: {attacker_data['wins']} wins, {attacker_data['losses']} losses, {attacker_data['fighting_style']} style"
    defender_summary = f"{defender_name}: {defender_data['wins']} wins, {defender_data['losses']} losses, {defender_data['fighting_style']} style"

    # Create a concise prompt
    prompt = (
        f"Hype the upcoming match between {attacker_name} and {defender_name} in a short, punchy paragraph. "
        f"{attacker_summary}. "
        f"{defender_summary}. "
        "Keep it under 300 characters, mention their key stats, and include a playful dig at Joey Logan's over-the-top credibility."
    )

    response = client.chat.completions.create(
        model="gpt-5.4-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a fight commentator for Bullshido, voiced by two parody announcers: Spike Oldberg and Joe Hogan. "
                    "Spike delivers dramatic callouts and energetic fight night lines. Joe offers breathless hype, ridiculous hot takes, and questionable credibility. "
                    "On occasion, mention the card girls Ariana Zebest, Whitney Balmer, Cruz de la Green, and Brookliyn Ninenine in a playful side comment. "
                    "Make it humorous, fast-paced, and clearly a satire of overenthusiastic fight commentary."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content


def generate_hype_challenge(
    user_config, attacker_id, defender_id, attacker_name, defender_name, wager: int = 0
):
    if not AI_AVAILABLE:
        return _fallback_hype(attacker_name, defender_name, wager)
    # Define relevant keys
    relevant_keys = [
        "training_level",
        "nutrition_level",
        "wins",
        "losses",
        "fighting_style",
        "intimidation_level",
    ]

    # Initialize data dictionaries
    attacker_data = {}
    defender_data = {}

    # Check if fighters have fought before
    if "fight_history" in user_config[str(attacker_id)]:
        fighting_history = user_config[str(attacker_id)]["fight_history"]
        for fight in fighting_history:
            if fight["opponent"] == defender_name:
                # Extract relevant data for attacker and defender from the past fight
                attacker_data = {
                    key: fight.get(key) for key in relevant_keys if key in fight
                }
                defender_data = {
                    key: user_config[str(defender_id)].get(key) for key in relevant_keys
                }
                break

    # If no past fight data is found, use the general data
    if not attacker_data:
        attacker_data = {
            key: user_config[str(attacker_id)].get(key) for key in relevant_keys
        }
    if not defender_data:
        defender_data = {
            key: user_config[str(defender_id)].get(key) for key in relevant_keys
        }


    if not attacker_data or not defender_data:
        return "Invalid attacker or defender ID."

    # Summarize the data to reduce token usage
    attacker_summary = f"{attacker_name}: {attacker_data['wins']} wins, {attacker_data['losses']} losses, {attacker_data['fighting_style']} style"
    defender_summary = f"{defender_name}: {defender_data['wins']} wins, {defender_data['losses']} losses, {defender_data['fighting_style']} style"

    # Create a concise prompt
    prompt = (
        f"Hype the upcoming match between {attacker_name} and {defender_name} in a short, punchy paragraph. "
        f"{attacker_summary}. "
        f"{defender_summary}. "
        f"There is a wager placed on this prize fight of {wager} and the winner takes double their wager. "
        "Keep it under 300 characters, mention their key stats, and include a playful dig at Joey Logan's over-the-top credibility."
    )

    response = client.chat.completions.create(
        model="gpt-5.4-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a fight commentator for Bullshido, voiced by two parody announcers: Spike Oldberg and Joe Hogan. "
                    "Spike delivers dramatic callouts and energetic fight night lines. Joe offers breathless hype, ridiculous hot takes, and questionable credibility. "
                    "On occasion, mention the card girls Ariana Zebest, Whitney Balmer, Cruz de la Green, and Brookliyn Ninenine in a playful side comment. "
                    "Lean into the satire of Joe claiming a grappler could beat a boxing legend, and keep the tone humorous and punchy."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content
