"""Small typed delivery vocabulary: controls never enter spoken text."""
import re

STYLES = {
    'neutral': 'Natural conversational delivery.',
    'skeptical': 'Dry, lightly amused sarcasm. Natural conversational delivery.',
    'pleased': 'Warm and amused. Natural conversational delivery.',
    'surprised': 'Playfully surprised. Normal speaking volume.',
    'scared': 'Playfully startled. Normal speaking volume, no scream.',
}


def delivery_instruction(expression, speed=1.0):
    style = STYLES.get(expression, STYLES['neutral'])
    if speed > 1.1:
        style += ' Speak briskly and clearly.'
    elif speed < .95:
        style += ' Speak at a relaxed pace.'
    return style


def clean_delivery_text(text):
    # Bracketed delivery tags are controls, never literal dialogue. Do not let
    # a model invent an unsupported tag and have a phonemizer read its name.
    return re.sub(r'\s+', ' ', re.sub(r'\[[^\]\n]{0,100}\]', ' ', text)).strip()
