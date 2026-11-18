"""Add AI insights and chat messages tables.

Revision ID: 0007_ai_insights_and_chat
Revises: 0006_transaction_header_detail
"""
from alembic import op
import sqlalchemy as sa


revision = '0007_ai_insights_and_chat'
down_revision = '0006_transaction_header_detail'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_insight',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tipe', sa.String(length=50), nullable=False),
        sa.Column('konten', sa.Text(), nullable=False),
        sa.Column('sumber', sa.String(length=50), nullable=False),
        sa.Column('dibuat_pada', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'ai_chat_message',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pengguna_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('pesan', sa.Text(), nullable=False),
        sa.Column('sumber', sa.String(length=50), nullable=False),
        sa.Column('dibuat_pada', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id']),
    )


def downgrade():
    op.drop_table('ai_chat_message')
    op.drop_table('ai_insight')
