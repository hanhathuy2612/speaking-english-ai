from app.core.config import get_settings
from app.models.conversation import Topic, TopicUnit
from app.models.role import ROLE_ADMIN, ROLE_USER, Role, UserRole
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_DEFAULT_TOPICS = [
    {
        "title": "Daily Routine",
        "description": "Talk about your day, habits, and schedule.",
        "level": "A2",
    },
    {
        "title": "Travel & Vacation",
        "description": "Discuss travel experiences, destinations and plans.",
        "level": "B1",
    },
    {
        "title": "Food & Cooking",
        "description": "Talk about your favorite food, recipes and restaurants.",
        "level": "A2",
    },
    {
        "title": "Work & Career",
        "description": "Discuss jobs, career goals and workplace experiences.",
        "level": "B1",
    },
    {
        "title": "Technology & AI",
        "description": "Explore tech trends, gadgets and AI in everyday life.",
        "level": "B2",
    },
    {
        "title": "Movies & TV Shows",
        "description": "Share opinions on films, series and your favorite genres.",
        "level": "B1",
    },
    {
        "title": "Health & Wellness",
        "description": "Talk about fitness, healthy habits and mental health.",
        "level": "B1",
    },
    {
        "title": "Environment",
        "description": "Discuss climate change, sustainability and eco-friendly habits.",
        "level": "B2",
    },
    {
        "title": "Education",
        "description": "Talk about learning experiences, schools and study tips.",
        "level": "A2",
    },
    {
        "title": "Culture & Traditions",
        "description": "Share cultural backgrounds, festivals and customs.",
        "level": "B1",
    },
]


async def seed_topics(session: AsyncSession) -> None:
    """Insert default topics if none exist."""
    result = await session.execute(select(Topic).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    for item in _DEFAULT_TOPICS:
        session.add(Topic(**item))
    await session.commit()


# Roadmap steps: keyed by exact topic title (matches seed topics).
_ROADMAP_BY_TOPIC_TITLE: dict[str, list[dict]] = {
    "Daily Routine": [
        {
            "sort_order": 1,
            "title": "Wake up and morning flow",
            "objective": "Describe what you usually do from waking up until you leave home.",
            "prompt_hint": "Ask about alarm, breakfast, and one habit. Encourage simple present tense.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "Work or study day",
            "objective": "Talk about a typical weekday: tasks, breaks, and how the day feels.",
            "prompt_hint": "Use work/study vocabulary; follow up on one specific activity they mention.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Evening wind-down",
            "objective": "Explain how you relax after dinner and what time you go to bed.",
            "prompt_hint": "Evening routines, hobbies, screens vs reading; keep tone friendly.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
    "Travel & Vacation": [
        {
            "sort_order": 1,
            "title": "Planning a trip",
            "objective": "Discuss where you want to go, when, and with whom.",
            "prompt_hint": "Destinations, transport, budget in simple questions.",
            "min_turns_to_complete": 2,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "At the airport or station",
            "objective": "Practice checking in, gates, and asking for help politely.",
            "prompt_hint": "Role-play staff lines; boarding pass, delays, luggage.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Hotel check-in",
            "objective": "Ask about the room, Wi‑Fi, and breakfast times.",
            "prompt_hint": "Reception dialogue; clarify dates and amenities.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 4,
            "title": "Asking locals for directions",
            "objective": "Give and follow directions to a landmark or café.",
            "prompt_hint": "Left/right, blocks, near the…; confirm understanding.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
}


async def seed_topic_units(session: AsyncSession) -> None:
    """Insert default topic units for seeded topics when units table is empty."""
    result = await session.execute(select(TopicUnit).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    topics_result = await session.execute(select(Topic))
    topics = {t.title: t for t in topics_result.scalars().all()}
    for title, units in _ROADMAP_BY_TOPIC_TITLE.items():
        topic = topics.get(title)
        if not topic:
            continue
        for u in units:
            session.add(TopicUnit(topic_id=topic.id, **u))
    await session.commit()


async def seed_roles_and_bootstrap(session: AsyncSession) -> None:
    """Ensure roles user/admin exist, every user has at least 'user', bootstrap admin emails."""
    for name in (ROLE_USER, ROLE_ADMIN):
        r = await session.execute(select(Role).where(Role.name == name))
        if r.scalar_one_or_none() is None:
            session.add(Role(name=name))
    await session.commit()

    r_user = (
        await session.execute(select(Role).where(Role.name == ROLE_USER))
    ).scalar_one()
    r_admin = (
        await session.execute(select(Role).where(Role.name == ROLE_ADMIN))
    ).scalar_one()

    users_result = await session.execute(select(User))
    users = list(users_result.scalars().all())
    for u in users:
        has_any = await session.execute(
            select(UserRole).where(UserRole.user_id == u.id).limit(1)
        )
        if has_any.scalar_one_or_none() is None:
            session.add(UserRole(user_id=u.id, role_id=r_user.id))
    await session.commit()

    settings = get_settings()
    emails = {
        e.strip().lower()
        for e in settings.bootstrap_admin_emails.split(",")
        if e.strip()
    }
    for u in users:
        if u.email.lower() not in emails:
            continue
        exists = await session.execute(
            select(UserRole).where(
                UserRole.user_id == u.id,
                UserRole.role_id == r_admin.id,
            )
        )
        if exists.scalar_one_or_none() is None:
            session.add(UserRole(user_id=u.id, role_id=r_admin.id))
    await session.commit()
