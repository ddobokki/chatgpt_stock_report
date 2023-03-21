import time

import openai


def make_requests(engine, prompts,api_key=None, organization=None):
    if api_key is not None:
        openai.api_key = api_key
    if organization is not None:
        openai.organization = organization
    retries = 3
    retry_cnt = 0
    backoff_time = 10
    while retry_cnt <= retries:
        try:
            response = openai.ChatCompletion.create(
                model=engine,
                messages = [{"role": "system","content":prompts}]
            )
            break
        except openai.error.OpenAIError as e:
            print(f"Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)
            backoff_time *= 1.5
            retry_cnt += 1
    return response