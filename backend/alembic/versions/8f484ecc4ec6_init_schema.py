"""init schema

Revision ID: 8f484ecc4ec6
Revises: 
Create Date: 2026-03-14 17:40:22.629179

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f484ecc4ec6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tables (order: topics, users, sessions, turns, scores)
    op.create_table(
        'topics',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('title', sa.VARCHAR(length=255), nullable=False),
        sa.Column('description', sa.TEXT(), nullable=True),
        sa.Column('level', sa.VARCHAR(length=20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('title'),
    )
    op.create_index('ix_topics_id', 'topics', ['id'], unique=False)
    op.create_table(
        'users',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('email', sa.VARCHAR(length=255), nullable=False),
        sa.Column('username', sa.VARCHAR(length=100), nullable=False),
        sa.Column('password_hash', sa.VARCHAR(length=255), nullable=False),
        sa.Column('is_active', sa.BOOLEAN(), nullable=False),
        sa.Column('created_at', sa.DATETIME(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_table(
        'sessions',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('user_id', sa.INTEGER(), nullable=False),
        sa.Column('topic_id', sa.INTEGER(), nullable=False),
        sa.Column('started_at', sa.DATETIME(), nullable=False),
        sa.Column('ended_at', sa.DATETIME(), nullable=True),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sessions_id', 'sessions', ['id'], unique=False)
    op.create_table(
        'turns',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('session_id', sa.INTEGER(), nullable=False),
        sa.Column('index_in_session', sa.INTEGER(), nullable=False),
        sa.Column('user_text', sa.TEXT(), nullable=False),
        sa.Column('assistant_text', sa.TEXT(), nullable=False),
        sa.Column('user_audio_path', sa.VARCHAR(length=512), nullable=True),
        sa.Column('assistant_audio_path', sa.VARCHAR(length=512), nullable=True),
        sa.Column('created_at', sa.DATETIME(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_turns_id', 'turns', ['id'], unique=False)
    op.create_table(
        'scores',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('turn_id', sa.INTEGER(), nullable=False),
        sa.Column('fluency', sa.FLOAT(), nullable=False),
        sa.Column('vocabulary', sa.FLOAT(), nullable=False),
        sa.Column('grammar', sa.FLOAT(), nullable=False),
        sa.Column('overall', sa.FLOAT(), nullable=False),
        sa.Column('feedback', sa.TEXT(), nullable=True),
        sa.ForeignKeyConstraint(['turn_id'], ['turns.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('turn_id'),
    )
    op.create_index('ix_scores_id', 'scores', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_scores_id', table_name='scores')
    op.drop_table('scores')
    op.drop_index('ix_turns_id', table_name='turns')
    op.drop_table('turns')
    op.drop_index('ix_sessions_id', table_name='sessions')
    op.drop_table('sessions')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_id', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')
    op.drop_index('ix_topics_id', table_name='topics')
    op.drop_table('topics')
