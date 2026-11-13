import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Menggunakan SQLite untuk tahap development. 
    # Untuk MySQL, ubah menjadi: 'mysql+pymysql://username:password@localhost/nama_database'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'toko_xwarti.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Set a persistent secret in the environment for deployments.
    SECRET_KEY = os.environ.get('SECRET_KEY')
