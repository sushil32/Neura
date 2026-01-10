# Voice Samples Directory

This directory stores voice samples for the NEURA TTS service.

## Built-in Voices

The TTS engine includes the following default voices:
- **Default Voice** - Standard XTTS neutral voice
- **Alex** - Clear, professional male voice
- **Sarah** - Warm, friendly female voice
- **Jordan** - Versatile, neutral voice

## Adding Custom (Cloned) Voices

To add a cloned voice:
1. Prepare a WAV audio sample (5-15 seconds recommended)
2. Use the `/voices/clone` API endpoint
3. The voice sample will be saved here as `{name}.wav`

## Requirements for Voice Samples
- Format: WAV (mono or stereo)
- Sample rate: 22050Hz or higher recommended
- Duration: 5-15 seconds of clear speech
- Quality: Clean audio without background noise
