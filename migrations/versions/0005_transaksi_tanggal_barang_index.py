"""Index sales date and item for daily forecasts.

Revision ID: 0005_transaksi_tanggal_barang_index
Revises: 0004_pengguna
"""
from alembic import op

revision = '0005_transaksi_tanggal_barang_index'
down_revision = '0004_pengguna'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'ix_transaksi_tanggal_barang',
        'transaksi',
        ['tanggal', 'barang_id'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_transaksi_tanggal_barang', table_name='transaksi')
