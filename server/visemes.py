"""Small cartoon viseme vocabulary from Kokoro's predicted phoneme durations.

Timing follows the pinned Kokoro pipeline's 600-sample duration units and its
three-frame BOS adjustment. This is synthesis timing, not forced alignment.
"""

def shape(phoneme):
    if phoneme in 'mbp': return 'closed'
    if phoneme in 'fv': return 'teeth'
    if phoneme in 'θðl': return 'tongue'
    if phoneme in 'uʊw': return 'pucker'
    if phoneme in 'oɔOQ': return 'round'
    if phoneme in 'aɑɒæʌIW': return 'open'
    if phoneme in 'iɪeɛɜɝjA': return 'wide'
    if phoneme.isspace() or phoneme in '.,!?;:—': return 'rest'
    if phoneme in 'ˈˌː': return 'rest'
    return 'narrow'


def cues(phonemes, durations, samples, offset=0):
    if len(durations) != len(phonemes)+2:
        raise ValueError('Phoneme duration alignment mismatch')
    cursor = max(0, int(durations[0])-3)*600
    result = []
    for phoneme, duration in zip(phonemes, durations[1:-1]):
        end = min(samples, cursor+int(duration)*600)
        mouth = shape(phoneme)
        if end > cursor:
            if result and result[-1][2] == mouth and result[-1][1] == offset+cursor:
                result[-1][1] = offset+end
            else:
                result.append([offset+cursor, offset+end, mouth])
        cursor = end
    return result
