import os

from dotenv import load_dotenv

load_dotenv()

POSTGRES_DSN = os.environ["POSTGRES_DSN"]
ELASTICSEARCH_URL = os.environ["ELASTICSEARCH_URL"]
ELASTICSEARCH_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "posts")
