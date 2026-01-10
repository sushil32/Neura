"""Seed default voices and avatars for NEURA."""
import asyncio
from app.database import init_db, async_session_maker
from app.models.voice import VoiceProfile
from app.models.avatar import Avatar
from sqlalchemy import select

DEFAULT_VOICES = [
    {
        "name": "Alex",
        "description": "Professional male voice, clear and articulate. Perfect for business presentations.",
        "language": "en",
        "gender": "male",
        "is_default": True,
        "is_public": True,
        "config": {
            "speed": 1.0,
            "pitch": 1.0,
            "style": "conversational",
            "emotion": "neutral",
            "provider": "coqui"
        }
    },
    {
        "name": "Sarah",
        "description": "Warm female voice with a friendly tone. Great for tutorials and explainers.",
        "language": "en",
        "gender": "female",
        "is_default": False,
        "is_public": True,
        "config": {
            "speed": 1.0,
            "pitch": 1.0,
            "style": "conversational",
            "emotion": "happy",
            "provider": "coqui"
        }
    },
    {
        "name": "James",
        "description": "Deep, authoritative male voice. Ideal for documentaries and narration.",
        "language": "en",
        "gender": "male",
        "is_default": False,
        "is_public": True,
        "config": {
            "speed": 0.95,
            "pitch": 0.9,
            "style": "formal",
            "emotion": "neutral",
            "provider": "coqui"
        }
    },
    {
        "name": "Emma",
        "description": "Energetic female voice with enthusiasm. Perfect for marketing content.",
        "language": "en",
        "gender": "female",
        "is_default": False,
        "is_public": True,
        "config": {
            "speed": 1.05,
            "pitch": 1.05,
            "style": "conversational",
            "emotion": "excited",
            "provider": "coqui"
        }
    },
    {
        "name": "David",
        "description": "Calm, soothing male voice. Best for meditation and wellness content.",
        "language": "en",
        "gender": "male",
        "is_default": False,
        "is_public": True,
        "config": {
            "speed": 0.9,
            "pitch": 0.95,
            "style": "storytelling",
            "emotion": "neutral",
            "provider": "coqui"
        }
    },
]

DEFAULT_AVATARS = [
    {
        "name": "Neura Default",
        "description": "The default NEURA AI assistant avatar.",
        "is_default": True,
        "is_public": True,
        "is_premium": False,
    },
    {
        "name": "Professional Male",
        "description": "Business-ready male presenter for corporate videos.",
        "is_default": False,
        "is_public": True,
        "is_premium": False,
    },
    {
        "name": "Professional Female",
        "description": "Business-ready female presenter for corporate videos.",
        "is_default": False,
        "is_public": True,
        "is_premium": False,
    },
]

async def seed_voices():
    """Seed default voices into the database."""
    await init_db()
    
    async with async_session_maker() as session:
        # Check existing voices
        result = await session.execute(select(VoiceProfile).where(VoiceProfile.is_public == True))
        existing = result.scalars().all()
        existing_names = {v.name for v in existing}
        
        added = 0
        for voice_data in DEFAULT_VOICES:
            if voice_data["name"] not in existing_names:
                voice = VoiceProfile(
                    user_id=None,  # System voice
                    **voice_data
                )
                session.add(voice)
                added += 1
                print(f"  + Added voice: {voice_data['name']}")
        
        if added > 0:
            await session.commit()
            print(f"\n✓ Added {added} new voices")
        else:
            print("✓ All default voices already exist")

async def seed_avatars():
    """Seed default avatars into the database."""
    async with async_session_maker() as session:
        # Check existing avatars
        result = await session.execute(select(Avatar).where(Avatar.is_public == True))
        existing = result.scalars().all()
        existing_names = {a.name for a in existing}
        
        # Get default voice for linking
        result = await session.execute(
            select(VoiceProfile).where(VoiceProfile.is_default == True, VoiceProfile.is_public == True)
        )
        default_voice = result.scalar_one_or_none()
        
        added = 0
        for avatar_data in DEFAULT_AVATARS:
            if avatar_data["name"] not in existing_names:
                avatar = Avatar(
                    user_id=None,  # System avatar
                    voice_id=default_voice.id if default_voice else None,
                    **avatar_data
                )
                session.add(avatar)
                added += 1
                print(f"  + Added avatar: {avatar_data['name']}")
        
        if added > 0:
            await session.commit()
            print(f"\n✓ Added {added} new avatars")
        else:
            print("✓ All default avatars already exist")

async def main():
    print("\n=== NEURA Database Seeder ===\n")
    
    print("Seeding voices...")
    await seed_voices()
    
    print("\nSeeding avatars...")
    await seed_avatars()
    
    print("\n=== Seeding Complete ===\n")

if __name__ == "__main__":
    asyncio.run(main())
