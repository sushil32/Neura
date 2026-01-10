
import asyncio
from app.database import init_db, get_db, async_session_maker
from app.models.user import User
from app.models.avatar import Avatar
from sqlalchemy import select

async def main():
    await init_db()
    
    async with async_session_maker() as session:
        print("\n=== USERS ===")
        result = await session.execute(select(User))
        users = result.scalars().all()
        for u in users:
            print(f"User: {u.id} | {u.email} | Credits: {u.credits}")

        print("\n=== AVATARS ===")
        result = await session.execute(select(Avatar))
        avatars = result.scalars().all()
        for a in avatars:
            print(f"Avatar: {a.id} | {a.name} | Owner: {a.user_id} | Public: {a.is_public} | Default: {a.is_default}")

if __name__ == "__main__":
    asyncio.run(main())
