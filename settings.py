import os

SERVER_NAME = "https://surfly-hipchat.herokuapp.com/"
SENTRY_DSN = os.environ.get('SENTRY_DSN')
SURFLY_API_KEY = os.environ.get('SURFLY_API_KEY')
HIPCHAT_AUTH_TOKEN = os.environ.get('HIPCHAT_AUTH_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
