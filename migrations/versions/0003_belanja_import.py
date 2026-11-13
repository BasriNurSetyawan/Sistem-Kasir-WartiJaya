"""Add separate purchase recap and detail ledgers.

Revision ID: 0003_belanja
Revises: 0002_revenue
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_belanja'
down_revision = '0002_revenue'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rekap_belanja',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('outlet', sa.String(length=150), nullable=False),
        sa.Column('tanggal_acuan', sa.Date(), nullable=False),
        sa.Column('tanggal_selesai', sa.Date(), nullable=True),
        sa.Column('cakupan', sa.String(length=30), nullable=False),
        sa.Column('keterangan_tanggal', sa.String(length=150), nullable=False),
        sa.Column('total', sa.Numeric(14, 2), nullable=False),
        sa.Column('source_file', sa.String(length=255), nullable=False),
        sa.Column('source_sha256', sa.String(length=64), nullable=False),
        sa.Column('source_sheet', sa.String(length=100), nullable=False),
        sa.Column('source_row', sa.Integer(), nullable=False),
        sa.CheckConstraint('total >= 0', name='ck_rekap_belanja_total_nonnegative'),
        sa.UniqueConstraint('source_sha256', 'source_sheet', 'source_row', name='uq_rekap_belanja_source_row'),
    )
    op.create_table(
        'detail_belanja',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('outlet', sa.String(length=150), nullable=False),
        sa.Column('tanggal', sa.Date(), nullable=False),
        sa.Column('nama_barang', sa.String(length=150), nullable=False),
        sa.Column('jumlah_asli', sa.String(length=100), nullable=False),
        sa.Column('harga_total', sa.Numeric(14, 2), nullable=False),
        sa.Column('kemungkinan_duplikat', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('source_file', sa.String(length=255), nullable=False),
        sa.Column('source_sha256', sa.String(length=64), nullable=False),
        sa.Column('source_sheet', sa.String(length=100), nullable=False),
        sa.Column('source_row', sa.Integer(), nullable=False),
        sa.CheckConstraint('harga_total >= 0', name='ck_detail_belanja_harga_nonnegative'),
        sa.UniqueConstraint('source_sha256', 'source_sheet', 'source_row', name='uq_detail_belanja_source_row'),
    )


def downgrade():
    op.drop_table('detail_belanja')
    op.drop_table('rekap_belanja')
