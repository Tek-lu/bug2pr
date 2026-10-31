import os, random, time
from dotenv import load_dotenv
from openai import APIStatusError, APITimeoutError, OpenAI, RateLimitError

load_dotenv()
client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"],
                timeout=300, max_retries=0)
MODEL = os.environ["LLM_MODEL"]


def chat(**kw):
    """Chat completion with retries on 429, 5xx and timeouts. 400s are raised immediately."""
    kw.setdefault("model", MODEL)
    for attempt in range(5):
        try:
            return client.chat.completions.create(**kw)
        except (RateLimitError, APITimeoutError, APIStatusError) as e:
            retryable = isinstance(e, (RateLimitError, APITimeoutError)) or e.status_code >= 500
            if not retryable or attempt == 4:
                raise
            time.sleep(0.5 * 2 ** attempt + random.uniform(0, 0.5))