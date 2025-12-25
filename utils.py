import time
import openai
from openai import OpenAI


def make_requests(engine, prompts=None, api_key=None, system_prompt=None, user_prompt=None):
    client = OpenAI(api_key= api_key)
    retries = 3
    retry_cnt = 0
    backoff_time = 10

    # Build messages array
    messages = []

    # Support both old style (prompts) and new style (system_prompt + user_prompt)
    if system_prompt and user_prompt:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    elif prompts:
        # Legacy support
        messages = [{"role": "user", "content": prompts}]
    else:
        raise ValueError("Either 'prompts' or both 'system_prompt' and 'user_prompt' must be provided")

    while retry_cnt <= retries:
        try:
            response = client.chat.completions.create(
                model=engine,
                messages=messages
            )
            break
        except:
            print(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)
            backoff_time *= 1.5
            retry_cnt += 1
    return response
