"""Add admin and cashier accounts.

Revision ID: 0004_pengguna
Revises: 0003_belanja
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_pengguna'
down_revision = '0003_belanja'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pengguna',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('aktif', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('dibuat_pada', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'kasir')", name='ck_pengguna_role_valid'),
    )


def downgrade():
    op.drop_table('pengguna')
