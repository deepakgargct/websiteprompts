import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import yake
from urllib.parse import urljoin, urlparse
import tldextract
import time

# --- Clean HTML Text ---
def extract_text_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "footer", "nav", "form"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)

# --- Crawl internal pages ---
def crawl_site(start_url, max_pages=5):
    visited = set()
    to_visit = [start_url]
    domain = tldextract.extract(start_url).registered_domain
    page_texts = []
    page_count = 0
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SEO-Crawler/1.0)"}
    progress = st.progress(0)

    while to_visit and page_count < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue

        try:
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code != 200:
                continue

            html = res.text
            text = extract_text_from_html(html)
            if len(text) > 300:
                page_texts.append(text)
                page_count += 1
                progress.progress(page_count / max_pages)

            visited.add(url)

            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = urljoin(url, a_tag["href"])
                href_parsed = urlparse(href)
                if (
                    href_parsed.scheme.startswith("http")
                    and domain in href_parsed.netloc
                    and href not in visited
                    and href not in to_visit
                ):
                    to_visit.append(href)

            time.sleep(0.5)  # polite crawl delay

        except Exception:
            continue

    return page_texts

# --- Extract keywords using YAKE ---
def extract_keywords_yake(text, max_phrases=30):
    kw_extractor = yake.KeywordExtractor(lan="en", n=3, top=max_phrases)
    keywords = kw_extractor.extract_keywords(text)
    return [kw for kw, score in keywords]

# --- Intent detection ---
def detect_intent(phrase):
    phrase = phrase.lower()
    blog_signals = ["how to", "benefits", "guide", "tips", "what is", "why", "explained"]
    product_signals = ["buy", "best", "vs", "review", "top", "comparison", "cheap"]
    service_signals = ["hire", "near me", "services", "company", "consultant", "provider", "freelancer"]

    if any(s in phrase for s in blog_signals):
        return "blog"
    if any(s in phrase for s in product_signals):
        return "product"
    if any(s in phrase for s in service_signals):
        return "service"
    return "blog"

# --- Streamlit App UI ---
st.title("🔎 Long-Tail Keyword Generator from Website (Multi-Page Crawl)")
st.markdown("Enter a website URL. This app will crawl pages, extract content, and generate keyword ideas with intent.")

url = st.text_input("Enter a website URL (e.g., https://example.com)")
max_pages = st.slider("Number of pages to crawl", 1, 20, 5)

if st.button("🚀 Crawl and Extract Keywords"):
    if not url.startswith("http"):
        st.warning("Please enter a valid URL starting with http or https.")
    else:
        with st.spinner("Crawling website and extracting keywords..."):
            pages = crawl_site(url, max_pages)
            full_text = " ".join(pages)

            if len(full_text) < 500:
                st.error("❌ Not enough content found to extract keywords.")
            else:
                phrases = extract_keywords_yake(full_text, max_phrases=50)
                results = []

                for phrase in phrases:
                    intent = detect_intent(phrase)
                    results.append({
                        "Keyword": phrase,
                        "Intent": intent,
                        "Source": url
                    })

                df = pd.DataFrame(results)
                st.success(f"✅ Extracted {len(df)} keywords from {len(pages)} pages.")
                st.dataframe(df)

                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download CSV", csv, "longtail_keywords.csv", "text/csv")
