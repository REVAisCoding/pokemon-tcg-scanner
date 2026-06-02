from models import GameType

POKEMON_VISION_PROMPT = """Analyze this Pokémon trading card image and extract visible card information.

Return JSON with exactly these fields:
{
  "name": "card name in the language printed on the card, or null if unreadable",
  "nameEnglish": "official English Pokémon name for API lookup (same as name if already English)",
  "number": "collector number only (e.g. '58' from '58/102'), or null",
  "set": "set/expansion name if visible, or null",
  "language": "language of the card text (e.g. 'Portuguese', 'English', 'Japanese'), or null",
  "confidence": "high, medium, or low — how confident you are in the name extraction"
}

Rules:
- Use the exact name as printed on the card.
- Always provide nameEnglish: translate the Pokémon name to English when the card is not in English.
  Examples: 'Rato' -> 'Rattata', 'Pikachu' -> 'Pikachu', 'Charizard' -> 'Charizard'.
- For number, return only the first part before the slash.
- confidence=low if the image is blurry, cropped, or the name is unclear.
- confidence=medium if you can read the name but set/number are uncertain.
- confidence=high if name is clearly readable and matches typical card layout.
- Return only valid JSON, no markdown."""

RIFTBOUND_VISION_PROMPT = """Analyze this Riftbound trading card image and extract visible card information.

Return JSON with exactly these fields:
{
  "name": "card name as printed on the card, or null if unreadable",
  "nameEnglish": "official English Riftbound card name for API lookup (same as name if already English)",
  "number": "collector number if visible, or null",
  "set": "set/expansion name if visible, or null",
  "language": "language of the card text (e.g. 'Portuguese', 'English'), or null",
  "confidence": "high, medium, or low — how confident you are in the name extraction"
}

Rules:
- Identify this as a Riftbound card, not Pokémon.
- Use the exact card name as printed (legend, unit, spell, gear, etc.).
- nameEnglish should be the canonical English card name used in Riftbound databases.
- confidence=low if the image is blurry, cropped, or the name is unclear.
- confidence=medium if you can read the name but set/number are uncertain.
- confidence=high if name is clearly readable and matches typical Riftbound card layout.
- Return only valid JSON, no markdown."""

MAGIC_VISION_PROMPT = """Identify this Magic: The Gathering card from the image. Return the most likely English card name, collector number if visible, set code if visible, and confidence.

Return JSON with exactly these fields:
{
  "name": "most likely English card name, or null if unreadable",
  "nameEnglish": "same as name — canonical English card name for database lookup",
  "number": "collector number only (e.g. '141' from '141/281'), or null",
  "set": "three-letter set code if visible (e.g. 'MOM', 'ONE', 'CLU'), or null",
  "language": "language of the card text (e.g. 'English', 'Portuguese'), or null",
  "confidence": "high, medium, or low — how confident you are in the identification"
}

Rules:
- Identify this as a Magic: The Gathering card, not Pokémon or Riftbound.
- Use the exact English card name when readable.
- For number, return only the collector number before the slash.
- For set, return the three-letter set code when visible, not the full set name.
- confidence=low if the image is blurry, cropped, or the name is unclear.
- confidence=medium if you can read the name but set/number are uncertain.
- confidence=high if name is clearly readable and matches typical Magic card layout.
- Return only valid JSON, no markdown."""

ONE_PIECE_VISION_PROMPT = """Analyze this One Piece Card Game trading card image and extract visible card information.

Return JSON with exactly these fields:
{
  "name": "card name as printed on the card, or null if unreadable",
  "nameEnglish": "official English One Piece TCG card name for API lookup (same as name if already English)",
  "number": "collector number only (e.g. '024' from 'OP01-024' or '024/121'), or null",
  "set": "set code if visible (e.g. 'OP-01', 'OP-02') or set name (e.g. 'Romance Dawn'), or null",
  "language": "language of the card text (e.g. 'English', 'Japanese'), or null",
  "confidence": "high, medium, or low — how confident you are in the name extraction"
}

Rules:
- Identify this as a One Piece Card Game card, not Pokémon, Magic, or Riftbound.
- Use the exact card name as printed (Leader, Character, Event, Stage, etc.).
- nameEnglish should be the canonical English card name used in One Piece TCG databases.
- For number, return only the numeric collector portion (e.g. '003' from 'OP01-003').
- For set, prefer the set code format OP-XX when visible; otherwise use the set name.
- confidence=low if the image is blurry, cropped, or the name is unclear.
- confidence=medium if you can read the name but set/number are uncertain.
- confidence=high if name is clearly readable and matches typical One Piece card layout.
- Return only valid JSON, no markdown."""

_VISION_PROMPTS: dict[GameType, str] = {
    "pokemon": POKEMON_VISION_PROMPT,
    "riftbound": RIFTBOUND_VISION_PROMPT,
    "magic": MAGIC_VISION_PROMPT,
    "onepiece": ONE_PIECE_VISION_PROMPT,
}


def get_vision_prompt(game_type: GameType) -> str:
    return _VISION_PROMPTS[game_type]
