from app.core.config import get_settings
from app.models.topic import Topic
from app.models.topic_unit import TopicUnit
from app.models.role import ROLE_ADMIN, ROLE_USER, Role, UserRole
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_DEFAULT_TOPICS = [
    {
        "title": "Daily Routine",
        "description": "Talk about your day, habits, and schedule.",
        "level": "5.5",
    },
    {
        "title": "Travel & Vacation",
        "description": "Discuss travel experiences, destinations and plans.",
        "level": "6",
    },
    {
        "title": "Food & Cooking",
        "description": "Talk about your favorite food, recipes and restaurants.",
        "level": "5.5",
    },
    {
        "title": "Work & Career",
        "description": "Discuss jobs, career goals and workplace experiences.",
        "level": "6",
    },
    {
        "title": "Technology & AI",
        "description": "Explore tech trends, gadgets and AI in everyday life.",
        "level": "6.5",
    },
    {
        "title": "Movies & TV Shows",
        "description": "Share opinions on films, series and your favorite genres.",
        "level": "6",
    },
    {
        "title": "Health & Wellness",
        "description": "Talk about fitness, healthy habits and mental health.",
        "level": "6",
    },
    {
        "title": "Environment",
        "description": "Discuss climate change, sustainability and eco-friendly habits.",
        "level": "6.5",
    },
    {
        "title": "Education",
        "description": "Talk about learning experiences, schools and study tips.",
        "level": "5.5",
    },
    {
        "title": "Culture & Traditions",
        "description": "Share cultural backgrounds, festivals and customs.",
        "level": "6",
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
    "Food & Cooking": [
        {
            "sort_order": 1,
            "title": "Favorite dishes",
            "objective": "Describe your favorite meal and why you like it.",
            "prompt_hint": "Taste, ingredients, and occasions. Encourage descriptive adjectives.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "Cooking at home",
            "objective": "Explain how you cook a simple dish step by step.",
            "prompt_hint": "Use sequence words like first, then, after that, finally.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Eating out",
            "objective": "Share a restaurant experience and compare dining options.",
            "prompt_hint": "Service, price, and atmosphere. Ask for opinions and reasons.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
    "Work & Career": [
        {
            "sort_order": 1,
            "title": "Current role",
            "objective": "Introduce your job or study path and daily responsibilities.",
            "prompt_hint": "Tasks, team, and schedule. Keep answers concrete.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "Career goals",
            "objective": "Talk about short-term and long-term career plans.",
            "prompt_hint": "Future tense and goal-setting language with clear reasons.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Interview practice",
            "objective": "Practice common interview questions with confident responses.",
            "prompt_hint": "Strengths, challenges, and examples from experience.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
    "Technology & AI": [
        {
            "sort_order": 1,
            "title": "Tech in daily life",
            "objective": "Discuss devices and apps you use every day.",
            "prompt_hint": "Benefits, habits, and one problem technology solves for you.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "AI tools at work or school",
            "objective": "Explain how AI helps with productivity and learning.",
            "prompt_hint": "Give practical examples and mention limitations.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Future of AI",
            "objective": "Debate opportunities and risks of AI in society.",
            "prompt_hint": "Encourage balanced arguments with supporting examples.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
    "Movies & TV Shows": [
        {
            "sort_order": 1,
            "title": "Favorite genres",
            "objective": "Describe movie or TV genres you enjoy and why.",
            "prompt_hint": "Plot, pacing, and emotional impact vocabulary.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "Review a film or series",
            "objective": "Give a short review with strengths and weaknesses.",
            "prompt_hint": "Storyline, acting, soundtrack, and recommendation.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Cinema vs streaming",
            "objective": "Compare watching at home and in theaters.",
            "prompt_hint": "Cost, convenience, and social experience comparison language.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
    "Health & Wellness": [
        {
            "sort_order": 1,
            "title": "Healthy routines",
            "objective": "Talk about habits that keep you physically healthy.",
            "prompt_hint": "Exercise, sleep, and diet vocabulary with frequency adverbs.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "Stress management",
            "objective": "Explain how you handle stress in busy periods.",
            "prompt_hint": "Coping methods, support systems, and realistic advice.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Public health discussion",
            "objective": "Discuss common health challenges in your community.",
            "prompt_hint": "Cause-effect language and practical solutions.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
    "Environment": [
        {
            "sort_order": 1,
            "title": "Daily eco habits",
            "objective": "Describe simple actions to reduce waste at home.",
            "prompt_hint": "Recycling, reusable items, and energy-saving behaviors.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "Climate change impacts",
            "objective": "Talk about visible environmental changes in your area.",
            "prompt_hint": "Weather patterns, pollution, and local observations.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Green solutions",
            "objective": "Propose practical environmental solutions for cities.",
            "prompt_hint": "Public transport, policy ideas, and community participation.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
    "Education": [
        {
            "sort_order": 1,
            "title": "Learning journey",
            "objective": "Share your study background and learning goals.",
            "prompt_hint": "Subjects, motivations, and challenges with examples.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "Study methods",
            "objective": "Explain techniques that help you learn effectively.",
            "prompt_hint": "Time management, note-taking, and revision strategies.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Education system opinions",
            "objective": "Discuss strengths and weaknesses of modern education.",
            "prompt_hint": "Critical thinking, exams, practical skills, and reform ideas.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
    "Culture & Traditions": [
        {
            "sort_order": 1,
            "title": "Cultural identity",
            "objective": "Introduce key customs from your hometown or country.",
            "prompt_hint": "Festivals, values, and family traditions with examples.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 2,
            "title": "Traditional celebrations",
            "objective": "Describe how an important festival is celebrated.",
            "prompt_hint": "Rituals, food, clothing, and community activities.",
            "min_turns_to_complete": 3,
            "min_avg_overall": None,
        },
        {
            "sort_order": 3,
            "title": "Tradition and modern life",
            "objective": "Discuss how traditions adapt in modern society.",
            "prompt_hint": "Compare old and new practices; support opinions with reasons.",
            "min_turns_to_complete": 3,
            "min_avg_overall": 6.0,
        },
    ],
}


async def seed_topic_units(session: AsyncSession) -> None:
    """Insert missing default topic units for seeded topics."""
    topics_result = await session.execute(select(Topic))
    topics = {t.title: t for t in topics_result.scalars().all()}

    existing_units_result = await session.execute(select(TopicUnit))
    existing_by_topic_sort: set[tuple[int, int]] = {
        (u.topic_id, u.sort_order) for u in existing_units_result.scalars().all()
    }

    created_any = False
    for title, units in _ROADMAP_BY_TOPIC_TITLE.items():
        topic = topics.get(title)
        if not topic:
            continue
        for u in units:
            if (topic.id, u["sort_order"]) in existing_by_topic_sort:
                continue
            session.add(TopicUnit(topic_id=topic.id, **u))
            created_any = True
    if created_any:
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
