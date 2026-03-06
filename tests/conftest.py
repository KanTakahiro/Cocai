from dotenv import load_dotenv

# Load .env so API keys are available for integration tests.
# Unit tests are not affected — they never read these keys.
load_dotenv()
