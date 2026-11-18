"""Add checkout headers and line-level transaction details.

Revision ID: 0006_transaction_header_detail
Revises: 0005_transaksi_tanggal_barang_index
"""
from alembic import op
import sqlalchemy as sa


revision = '0006_transaction_header_detail'
down_revision = '0005_transaksi_tanggal_barang_index'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'transaksi_header',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tanggal', sa.Date(), nullable=False),
        sa.Column('dibuat_pada', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'detail_transaksi',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('transaksi_id', sa.Integer(), nullable=False),
        sa.Column('barang_id', sa.Integer(), nullable=False),
        sa.Column('jumlah_terjual', sa.Integer(), nullable=False),
        sa.Column('harga_satuan', sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint('jumlah_terjual > 0', name='ck_detail_transaksi_jumlah_positive'),
        sa.CheckConstraint('harga_satuan >= 0', name='ck_detail_transaksi_harga_nonnegative'),
        sa.ForeignKeyConstraint(
            ['transaksi_id'], ['transaksi_header.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(['barang_id'], ['barang.id']),
    )
    op.create_index('ix_detail_transaksi_barang', 'detail_transaksi', ['barang_id'])


def downgrade():
    op.drop_index('ix_detail_transaksi_barang', table_name='detail_transaksi')
    op.drop_table('detail_transaksi')
    op.drop_table('transaksi_header')
