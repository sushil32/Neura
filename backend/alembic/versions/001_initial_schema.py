"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.Text, nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('plan', sa.String(50), default='free'),
        sa.Column('credits', sa.Integer, default=100),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_verified', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('refresh_token', sa.Text, unique=True, nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('is_revoked', sa.Boolean, default=False),
    )
    
    # Voice profiles table
    op.create_table(
        'voice_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('language', sa.String(10), default='en'),
        sa.Column('gender', sa.String(20), nullable=True),
        sa.Column('sample_path', sa.Text, nullable=True),
        sa.Column('model_path', sa.Text, nullable=True),
        sa.Column('config', postgresql.JSON, nullable=True),
        sa.Column('preview_url', sa.Text, nullable=True),
        sa.Column('is_default', sa.Boolean, default=False),
        sa.Column('is_public', sa.Boolean, default=False),
        sa.Column('is_cloned', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Avatars table
    op.create_table(
        'avatars',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('voice_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('voice_profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('model_path', sa.Text, nullable=True),
        sa.Column('thumbnail_url', sa.Text, nullable=True),
        sa.Column('config', postgresql.JSON, nullable=True),
        sa.Column('is_default', sa.Boolean, default=False),
        sa.Column('is_public', sa.Boolean, default=False),
        sa.Column('is_premium', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Videos table
    op.create_table(
        'videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('avatar_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('avatars.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('type', sa.String(50), default='custom'),
        sa.Column('status', sa.String(50), default='draft', index=True),
        sa.Column('script', sa.Text, nullable=True),
        sa.Column('prompt', sa.Text, nullable=True),
        sa.Column('video_url', sa.Text, nullable=True),
        sa.Column('thumbnail_url', sa.Text, nullable=True),
        sa.Column('audio_url', sa.Text, nullable=True),
        sa.Column('duration', sa.Integer, nullable=True),
        sa.Column('resolution', sa.String(20), nullable=True),
        sa.Column('file_size', sa.Integer, nullable=True),
        sa.Column('metadata', postgresql.JSON, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('credits_used', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
    )
    
    # Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('type', sa.String(50), nullable=False, index=True),
        sa.Column('status', sa.String(50), default='pending', index=True),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('progress', sa.Float, default=0.0),
        sa.Column('current_step', sa.String(255), nullable=True),
        sa.Column('input_data', postgresql.JSON, nullable=True),
        sa.Column('result', postgresql.JSON, nullable=True),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('celery_task_id', sa.String(255), nullable=True),
        sa.Column('credits_estimated', sa.Integer, default=0),
        sa.Column('credits_used', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
    )
    
    # Credits history table
    op.create_table(
        'credits_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('amount', sa.Integer, nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('balance_after', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('credits_history')
    op.drop_table('jobs')
    op.drop_table('videos')
    op.drop_table('avatars')
    op.drop_table('voice_profiles')
    op.drop_table('sessions')
    op.drop_table('users')

