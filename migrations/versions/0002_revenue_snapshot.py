"""Store exact prices and transaction revenue snapshots.

Revision ID: 0002_revenue
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_revenue'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('barang') as batch:
        batch.alter_column(
            'harga', existing_type=sa.Float(), type_=sa.Numeric(14, 2),
            existing_nullable=False,
        )
        batch.alter_column(
            'stok', existing_type=sa.Integer(), nullable=False,
        )
        batch.create_check_constraint('ck_barang_stok_nonnegative', 'stok >= 0')
        batch.create_check_constraint('ck_barang_harga_nonnegative', 'harga >= 0')

    with op.batch_alter_table('transaksi') as batch:
        batch.add_column(sa.Column('harga_satuan', sa.Numeric(14, 2), nullable=True))
    op.execute(sa.text(
        'UPDATE transaksi SET harga_satuan = '
        '(SELECT barang.harga FROM barang WHERE barang.id = transaksi.barang_id)'
    ))
    with op.batch_alter_table('transaksi') as batch:
        batch.alter_column('harga_satuan', existing_type=sa.Numeric(14, 2), nullable=False)
        batch.alter_column('tanggal', existing_type=sa.Date(), nullable=False)
        batch.create_check_constraint('ck_transaksi_jumlah_positive', 'jumlah_terjual > 0')
        batch.create_check_constraint('ck_transaksi_harga_nonnegative', 'harga_satuan >= 0')


def downgrade():
    with op.batch_alter_table('transaksi') as batch:
        batch.drop_constraint('ck_transaksi_harga_nonnegative', type_='check')
        batch.drop_constraint('ck_transaksi_jumlah_positive', type_='check')
        batch.drop_column('harga_satuan')
    with op.batch_alter_table('barang') as batch:
        batch.drop_constraint('ck_barang_harga_nonnegative', type_='check')
        batch.drop_constraint('ck_barang_stok_nonnegative', type_='check')
        batch.alter_column(
            'harga', existing_type=sa.Numeric(14, 2), type_=sa.Float(),
            existing_nullable=False,
        )
