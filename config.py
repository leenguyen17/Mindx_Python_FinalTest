import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-change-me')
API_KEY = os.getenv('API_KEY', '')
APP_USERNAME = os.getenv('APP_USERNAME', 'admin')
APP_PASSWORD = os.getenv('APP_PASSWORD', 'netflix2024')
CSV_PATH = os.path.join(os.path.dirname(__file__), 'data', 'netflix_titles.csv')
