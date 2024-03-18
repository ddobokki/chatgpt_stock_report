import time
import openai
from openai import OpenAI


def make_requests(engine, prompts,api_key=None, organization=None):
    client = OpenAI(api_key= api_key)
    retries = 3
    retry_cnt = 0
    backoff_time = 10
    while retry_cnt <= retries:
        try:
            response = client.chat.completions.create(
                model=engine,
                messages = [{"role": "user","content":prompts}]
            )
            break
        except:
            print(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)
            backoff_time *= 1.5
            retry_cnt += 1
    return response
