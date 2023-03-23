import argparse
import os
import re
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from utils import make_requests


def main(args):

    base_url = 'https://finance.naver.com/research/'
    list_url = base_url + "company_list.naver"

    ## 1page에 있는 url들을 크롤링함
    response = requests.get(list_url)
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    report_raw_tags = soup.select('#contentarea_left > div > table > tr > td > a')

    report_urls = []
    for report_raw_tag in report_raw_tags:
        if report_raw_tag.attrs['href'].startswith('company'):
            report_urls.append(base_url + report_raw_tag.attrs['href'])
    ###############################################################################

    # 각 url에서 그날의 레포트를 크롤링함
    datetime_utc = datetime.utcnow()
    datetime_kst = datetime_utc + timedelta(hours=9)
    today = datetime_kst.today().date().strftime('%Y.%m.%d')
    folder_path = today.replace('.','/')

    os.makedirs(folder_path,exist_ok=True)

    reports = []
    for report_url in report_urls:
        report_response = requests.get(report_url)
        report_html = report_response.text
        report_soup = BeautifulSoup(report_html, 'html.parser')

        tags = report_soup.select('#contentarea_left > div > table > tr')
        report = ''
        for tag in tags:
            tag_text = tag.text.replace('\t','').lstrip().rstrip()
            report += tag_text + '\n'
        report_day = re.search(r"\d{4}\.\d{2}\.\d{2}",report).group()
        if not report_day == today:
            break
        reports.append(report)

    ############################################################################
    base_prompt = """
    The text below is a stock report on a company.
    Please summarize it in Korean.
    
    The format is as follows
    ## Company name
    - Summary
    
    리포트:
    """
    summary = [f'# {today} stock report']
    for report in tqdm(reports):
        prompt = base_prompt + report
        try:
            chat_gpt_response = make_requests(engine = "gpt-3.5-turbo-0301",prompts=prompt,api_key=args.api_key, organization=args.organization)
            summary.append(chat_gpt_response["choices"][0]["message"]["content"])
        except:
            continue

    with open(os.path.join(folder_path,'README.md'), 'w') as file:
        file.write('\n'.join(summary))

    with open('README.md', 'w') as file:
        file.write('\n'.join(summary))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api_key",
        type=str,
        default="",
    )
    parser.add_argument(
        "--organization",
        type=str,
        default="",
    )
    args = parser.parse_args()

    main(args)

