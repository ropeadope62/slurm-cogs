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
OPENAI_MODEL = os.getenv("BULLSHIDO_OPENAI_MODEL", "gpt-4o-mini")
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


def _get_fighter_summaries(
    user_config, attacker_id, defender_id, attacker_name, defender_name
):
    relevant_keys = [
        "training_level",
        "nutrition_level",
        "wins",
        "losses",
        "fighting_style",
        "intimidation_level",
    ]

    attacker_data = {}
    defender_data = {}

    if "fight_history" in user_config[str(attacker_id)]:
        fighting_history = user_config[str(attacker_id)]["fight_history"]
        for fight in fighting_history:
            if fight["opponent"] == defender_name:
                attacker_data = {
                    key: fight.get(key) for key in relevant_keys if key in fight
                }
                defender_data = {
                    key: user_config[str(defender_id)].get(key) for key in relevant_keys
                }
                break

    if not attacker_data:
        attacker_data = {
            key: user_config[str(attacker_id)].get(key) for key in relevant_keys
        }
    if not defender_data:
        defender_data = {
            key: user_config[str(defender_id)].get(key) for key in relevant_keys
        }

    if not attacker_data or not defender_data:
        return None, None

    attacker_summary = (
        f"{attacker_name}: {attacker_data['wins']} wins, "
        f"{attacker_data['losses']} losses, {attacker_data['fighting_style']} style"
    )
    defender_summary = (
        f"{defender_name}: {defender_data['wins']} wins, "
        f"{defender_data['losses']} losses, {defender_data['fighting_style']} style"
    )
    return attacker_summary, defender_summary


def _create_hype_completion(prompt: str, system_prompt: str):
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def generate_hype(user_config, attacker_id, defender_id, attacker_name, defender_name):
    if not AI_AVAILABLE:
        return _fallback_hype(attacker_name, defender_name)

    attacker_summary, defender_summary = _get_fighter_summaries(
        user_config, attacker_id, defender_id, attacker_name, defender_name
    )
    if not attacker_summary or not defender_summary:
        return "Invalid attacker or defender ID."

    # Create a concise prompt
    prompt = (
        f"Hype the upcoming match between {attacker_name} and {defender_name} in a short, punchy paragraph. "
        f"{attacker_summary}. "
        f"{defender_summary}. "
        "Keep it under 300 characters, mention their key stats, and include a playful dig at Joey Logan's over-the-top credibility."
    )
    system_prompt = (
        "You are a fight commentator for Bullshido, voiced by two parody announcers: Spike Oldberg and Joe Hogan. "
        "Spike delivers dramatic callouts and energetic fight night lines. Joe offers breathless hype, ridiculous hot takes, and questionable credibility. "
        "On occasion, mention the card girls Ariana Zebest, Whitney Balmer, Cruz de la Green, and Brookliyn Ninenine in a playful side comment. "
        "Make it humorous, fast-paced, and clearly a satire of overenthusiastic fight commentary."
    )

    return _create_hype_completion(prompt, system_prompt)


def generate_hype_challenge(
    user_config, attacker_id, defender_id, attacker_name, defender_name, wager: int = 0
):
    if not AI_AVAILABLE:
        return _fallback_hype(attacker_name, defender_name, wager)

    attacker_summary, defender_summary = _get_fighter_summaries(
        user_config, attacker_id, defender_id, attacker_name, defender_name
    )
    if not attacker_summary or not defender_summary:
        return "Invalid attacker or defender ID."

    # Create a concise prompt
    prompt = (
        f"Hype the upcoming match between {attacker_name} and {defender_name} in a short, punchy paragraph. "
        f"{attacker_summary}. "
        f"{defender_summary}. "
        f"There is a wager placed on this prize fight of {wager} and the winner takes double their wager. "
        "Keep it under 300 characters, mention their key stats, and include a playful dig at Joey Logan's over-the-top credibility."
    )
    system_prompt = (
        "You are a fight commentator for Bullshido, voiced by two parody announcers: Spike Oldberg and Joe Hogan. "
        "Spike delivers dramatic callouts and energetic fight night lines. Joe offers breathless hype, ridiculous hot takes, and questionable credibility. "
        "On occasion, mention the card girls Ariana Zebest, Whitney Balmer, Cruz de la Green, and Brookliyn Ninenine in a playful side comment. "
        "Lean into the satire of Joe claiming a grappler could beat a boxing legend, and keep the tone humorous and punchy."
    )

    return _create_hype_completion(prompt, system_prompt)


def generate_hype_safe(
    user_config, attacker_id, defender_id, attacker_name, defender_name
):
    try:
        return generate_hype(
            user_config, attacker_id, defender_id, attacker_name, defender_name
        )
    except Exception:
        return _fallback_hype(attacker_name, defender_name)


def generate_hype_challenge_safe(
    user_config, attacker_id, defender_id, attacker_name, defender_name, wager: int = 0
):
    try:
        return generate_hype_challenge(
            user_config,
            attacker_id,
            defender_id,
            attacker_name,
            defender_name,
            wager,
        )
    except Exception:
        return _fallback_hype(attacker_name, defender_name, wager)
