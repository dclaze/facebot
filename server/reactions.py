"""Typed provider output. Expression controls are never spoken or executed as code."""
import json

EXPRESSIONS = ('neutral', 'skeptical', 'surprised', 'scared', 'pleased')
REPLY_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['speech', 'expression'],
    'properties': {
        'speech': {'type': 'string', 'maxLength': 160},
        'expression': {'type': 'string', 'enum': list(EXPRESSIONS)},
    },
}


def parse_reply(text):
    """Fail closed: malformed control output cannot become phonemizer input."""
    value = json.loads(text)
    if not isinstance(value, dict) or set(value) != {'speech', 'expression'}:
        raise ValueError('Invalid reply envelope')
    speech, expression = value['speech'], value['expression']
    if not isinstance(speech, str) or len(speech) > 160 or len(speech.split()) > 32:
        raise ValueError('Speech exceeds short reply budget')
    if expression not in EXPRESSIONS:
        raise ValueError('Unsupported expression')
    return speech, {'type': 'expression', 'name': expression, 'duration_ms': 1800}


def validate_expression(value):
    return (isinstance(value, dict) and set(value) == {'type', 'name', 'duration_ms'}
            and value['type'] == 'expression' and value['name'] in EXPRESSIONS
            and type(value['duration_ms']) is int and 100 <= value['duration_ms'] <= 2500)
