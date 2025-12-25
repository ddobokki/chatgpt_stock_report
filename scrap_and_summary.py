import argparse
import os
import re
from datetime import date, datetime, timedelta, timezone
import tempfile
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import fitz  # PyMuPDF

from utils import make_requests


def detect_pdf_link(soup, base_url):
    """
    Detect PDF download link from BeautifulSoup object
    Returns: PDF URL or None
    """
    # Try CSS selector for .pdf extension first
    pdf_links = soup.select("a[href$='.pdf']")
    if pdf_links:
        href = pdf_links[0].get("href")
        return construct_full_url(base_url, href)

    # Try searching for PDF indicators in link text
    for link in soup.find_all("a"):
        link_text = link.text.upper()
        href = link.get("href", "").lower()
        if "PDF" in link_text or ".pdf" in href:
            return construct_full_url(base_url, link.get("href"))

    return None


def construct_full_url(base_url, href):
    """Handle relative and absolute URLs"""
    if href.startswith("http"):
        return href
    return urljoin(base_url, href)


def extract_text_from_pdf(pdf_url):
    """
    Download and extract text from PDF
    Returns: extracted text or None on failure
    """
    temp_pdf_path = None
    try:
        # Download PDF to temp file
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(response.content)
            temp_pdf_path = tmp.name

        # Extract text using PyMuPDF
        text = ""
        doc = fitz.open(temp_pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()

        return text

    except Exception as e:
        print(f"PDF extraction failed: {e}")
        return None
    finally:
        # Cleanup temp file
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)


def extract_text_from_html(soup):
    """
    Extract text from HTML (current method)
    Returns: extracted text
    """
    tags = soup.select("#contentarea_left > div > table > tr")
    report = ""
    for tag in tags:
        tag_text = tag.text.replace("\t", "").lstrip().rstrip()
        report += tag_text + "\n"
    return report


def extract_company_name(summary_text):
    """
    Extract company name from summary text
    Returns: company name or None
    """
    # Look for ## [회사명] pattern
    match = re.search(r"##\s*\[?([^\]]+?)\]?(?:\s*\n|$)", summary_text)
    if match:
        return match.group(1).strip()

    # Fallback: look for ## followed by text
    match = re.search(r"##\s+(.+?)(?:\s*\n|$)", summary_text)
    if match:
        return match.group(1).strip()

    return "Unknown"


def process_and_sort_summaries(summaries):
    """
    Process summaries: add numbering for duplicates and sort by company name
    Returns: list of processed summaries
    """
    # Extract company names and pair with summaries
    summary_data = []
    for summary in summaries:
        company_name = extract_company_name(summary)
        summary_data.append({"company": company_name, "content": summary})

    # Sort by company name
    summary_data.sort(key=lambda x: x["company"])

    # First pass: count total occurrences of each company
    company_totals = {}
    for item in summary_data:
        company = item["company"]
        company_totals[company] = company_totals.get(company, 0) + 1

    # Second pass: add numbering to all items of companies with duplicates
    company_current_counts = {}
    processed_summaries = []

    for item in summary_data:
        company = item["company"]
        content = item["content"]

        # Track current count for this company
        if company not in company_current_counts:
            company_current_counts[company] = 0
        company_current_counts[company] += 1

        # Add number if company appears more than once
        if company_totals[company] > 1:
            # Replace company name with numbered version
            content = re.sub(
                r"(##\s*\[?)(" + re.escape(company) + r")(\]?)",
                r"\1\2 (" + str(company_current_counts[company]) + r")\3",
                content,
                count=1,
            )

        processed_summaries.append(content)

    return processed_summaries


def main(args):

    base_url = "https://finance.naver.com/research/"
    list_url = base_url + "company_list.naver"

    ## 1page에 있는 url들을 크롤링함
    response = requests.get(list_url)
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    report_raw_tags = soup.select("#contentarea_left > div > table > tr > td > a")

    report_urls = []
    for report_raw_tag in report_raw_tags:
        if report_raw_tag.attrs["href"].startswith("company"):
            report_urls.append(base_url + report_raw_tag.attrs["href"])
    ###############################################################################

    # 각 url에서 그날의 레포트를 크롤링함
    datetime_utc = datetime.utcnow()
    datetime_kst = datetime_utc + timedelta(hours=9)
    today = datetime_kst.today().date().strftime("%Y.%m.%d")
    folder_path = today.replace(".", "/")

    os.makedirs(folder_path, exist_ok=True)

    reports = []
    for report_url in report_urls:
        try:
            report_response = requests.get(report_url, timeout=30)
            report_response.raise_for_status()
            report_html = report_response.text
            report_soup = BeautifulSoup(report_html, "html.parser")

            # Try to detect and extract from PDF first
            pdf_url = detect_pdf_link(report_soup, report_url)

            if pdf_url:
                report = extract_text_from_pdf(pdf_url)

                # If PDF extraction failed, fall back to HTML
                if not report:
                    report = extract_text_from_html(report_soup)
            else:
                # No PDF found, use HTML extraction
                report = extract_text_from_html(report_soup)

            # Date validation
            date_match = re.search(r"\d{4}\.\d{2}\.\d{2}", report)
            if not date_match:
                continue  # Skip if no date found

            report_day = date_match.group()
            if not report_day == today:
                break

            reports.append(report)

        except requests.RequestException as e:
            print(f"Failed to fetch {report_url}: {e}")
            continue
        except Exception as e:
            print(f"Error processing {report_url}: {e}")
            continue

    ############################################################################
    # Load prompt from file
    prompt_file_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
    with open(prompt_file_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    # Generate summaries
    raw_summaries = []
    for report in tqdm(reports):
        try:
            chat_gpt_response = make_requests(
                engine="gpt-5-mini",
                system_prompt=base_prompt,
                user_prompt=report,
                api_key=args.api_key,
            )
            raw_summaries.append(chat_gpt_response.choices[0].message.content)
        except:
            continue

    # Process summaries: sort by company name and add numbering for duplicates
    processed_summaries = process_and_sort_summaries(raw_summaries)

    # Generate market insight from all summaries
    market_insight = ""
    if processed_summaries:
        try:
            # Load insight prompt
            insight_prompt_path = os.path.join(os.path.dirname(__file__), "insight_prompt.txt")
            with open(insight_prompt_path, "r", encoding="utf-8") as f:
                insight_system_prompt = f.read()

            # Combine all summaries for analysis
            all_summaries_text = "\n\n---\n\n".join(processed_summaries)

            # Request market insight
            insight_response = make_requests(
                engine="gpt-5",
                system_prompt=insight_system_prompt,
                user_prompt=all_summaries_text,
                api_key=args.api_key,
            )
            market_insight = insight_response.choices[0].message.content
        except Exception as e:
            print(f"Failed to generate market insight: {e}")
            market_insight = ""

    # Build final summary with insight at the top
    final_summary = [f"# {today} stock report"]

    if market_insight:
        final_summary.append(market_insight)
        final_summary.append("---\n\n## 📋 개별 종목 리포트")

    final_summary.extend(processed_summaries)

    with open(os.path.join(folder_path, "README.md"), "w") as file:
        file.write("\n\n".join(final_summary))

    with open("README.md", "w") as file:
        file.write("\n\n".join(final_summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api_key",
        type=str,
        default="",
    )
    args = parser.parse_args()

    main(args)
