
import re

def clean_text_for_tts(text: str) -> str:
    """Clean text before sending to TTS service."""
    if not text:
        return ""
        
    # Remove timestamps/section headers like [0:00 - 0:10 | Hook]
    text = re.sub(r'\[\d{1,2}:\d{2}.*?\]', '', text)
    
    # Remove visual cues like [VISUAL: ...]
    text = re.sub(r'\[vis.*?\]', '', text, flags=re.IGNORECASE)
    
    # Remove standalone headers (e.g. "Title | Topic")
    # Heuristic: line contains "|" and is short
    lines = []
    for line in text.split('\n'):
        if '|' in line and len(line) < 100:
            continue
        lines.append(line)
    text = '\n'.join(lines)
    
    # Replace [PAUSE] or similar tags with breaks
    text = re.sub(r'\[pause.*?\]', '... ', text, flags=re.IGNORECASE)
    
    # Clean extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

script = """AARAV-X | What’s New in AI (2 Minutes)

[0:00 – 0:10 | Hook]
Hey everyone, this is Aarav-X.
AI is evolving faster than ever, and what felt futuristic last year is already normal today.
In the next two minutes, here’s what’s new in AI right now.

[0:10 – 0:40 | Multimodal AI]
First, AI is no longer limited to text.
Today’s models can understand images, audio, video, and documents together.
This makes real-time AI tutors, smart assistants, and advanced content analysis possible, all in one system.

[VISUAL: Show robotic arm]
[1:30 – 1:50 | AI Agents]
Next is the rise of AI agents.
These systems can plan tasks, make decisions, and execute actions autonomously.
Instead of just answering questions, AI is starting to work like a digital assistant or teammate.

[PAUSE]
Follow AARAV-X for clear and simple updates on the future of AI."""

cleaned = clean_text_for_tts(script)
print("Original Length:", len(script))
print("Cleaned Length:", len(cleaned))
print("-" * 40)
print(cleaned)
print("-" * 40)

if "AARAV-X |" in cleaned:
    print("FAIL: Title not removed")
if "[0:00" in cleaned:
    print("FAIL: Timestamp not removed")
if "[VISUAL" in cleaned:
    print("FAIL: Visual cue not removed")
if "[PAUSE]" in cleaned:
    print("FAIL: PAUSE tag not replaced")
    
if "..." in cleaned:
    print("SUCCESS: PAUSE replaced with ellipsis")
