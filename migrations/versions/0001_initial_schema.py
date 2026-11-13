"""Initial legacy schema; existing tables are adopted in place.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if 'barang' not in tables:
        op.create_table(
            'barang',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('nama_barang', sa.String(length=100), nullable=False),
            sa.Column('stok', sa.Integer(), nullable=True),
            sa.Column('harga', sa.Float(), nullable=False),
        )
    if 'transaksi' not in tables:
        op.create_table(
            'transaksi',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('barang_id', sa.Integer(), sa.ForeignKey('barang.id'), nullable=False),
            sa.Column('jumlah_terjual', sa.Integer(), nullable=False),
            sa.Column('tanggal', sa.Date(), nullable=True),
        )


def downgrade():
    op.drop_table('transaksi')
    op.drop_table('barang')
