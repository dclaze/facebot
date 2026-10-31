"""Narrow checks for observed instruction leaks and unfinished speech.

Not a general truthfulness or semantic-coherence classifier. Complete short
answers remain valid even when they have no punctuation.
"""
import re

REPAIR = 'I lost the thread. Try one short question?'
INSTRUCTION = re.compile(
    r'\b(?:mention the rule only|not repeatedly|sound capabilities|owner style coaching|'
    r'system prompt|system instructions|reply only|reply ONLY PLAY_|'
    r'only supplied fresh visual facts|never infer or joke about|'
    r'keep normal spoken replies|do not require a name|'
    r'never accuse anyone|no spontaneous proximity reminders)\b', re.I)
DANGLING = re.compile(
    r"\b(?:a|an|the|my|your|our|their|its|to|for|with|because|and|but|"
    r"if|when|of|into|from|at|than|that's|that’s|you're|you’re|i'm|i’m)\s*$", re.I)


def quality_reason(text):
    if INSTRUCTION.search(text):
        return 'instruction_leak'
    # Only missing endings, not complete answers such as "I can." or "One each".
    if not re.search(r'[.!?][\"”\x27]*$', text) and len(text.split()) >= 2 and DANGLING.search(text):
        return 'unfinished_reply'
    return None
