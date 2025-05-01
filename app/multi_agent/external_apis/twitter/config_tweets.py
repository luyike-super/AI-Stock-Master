from dotenv import load_dotenv
import os
load_dotenv()
class TwitterConfig:
    # Twitter API配置
    ENABLED = True
    BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
    TARGET_USERS = ["yua_mikami", "BTCBruce1", "elonmusk"]
    INTERVAL_MINUTES = 30
    OUTPUT_DIR = "./data/tweets"
    MAX_RESULTS_PER_USER = 1