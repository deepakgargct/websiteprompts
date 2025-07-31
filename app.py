import streamlit as st
import requests
from bs4 import BeautifulSoup
import spacy
import pandas as pd
from urllib.parse import urljoin, urlparse
import tldextract
import time

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# --- Utility: Extract clean text from HTML ---
def extract_text_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "footer", "nav", "form"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return text

# --- Crawl internal links ---
def crawl_site(start_url, max_pages=5):
    visited = set()
    to_visit = [start_url]
    domain = tldextract.extract(start_url).registered_domain
    page_texts = []

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue

        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                continue

            html = res.text
            text = extract_text_from_html(html)
            page_texts.append(text)
            visited.add(url)

            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = urljoin(url, a_tag["href"])
                href_parsed = urlparse(href)
                if href_parsed.scheme.startswith("http") and domain in href_parsed.netloc:
                    if href not in visited and href not in to_visit:
                        to_visit.append(href)

            time.sleep(1)  # Be nice to servers

        except Exception as e:
            continue

    return page_texts

# --- Extract long-tail phrases ---
def extract_keywords(text, max_phrases=30):
    doc = nlp(text)
    phrases = set()

    for chunk in doc.noun_chunks:
        phrase = chunk.text.strip().lower()
        if 2 <= len(phrase.split()) <= 6:
            phrases.add(phrase)

    phrases = list(phrases)
    phrases.sort(key=lambda x: (-len(x), x))
    return phrases[:max_phrases]

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

# --- Streamlit App ---
st.title("🔎 Website Crawler + Long-Tail Keyword Extractor")

url = st.text_input("Enter a starting website URL (e.g., https://example.com)")
max_pages = st.slider("How many pages to crawl?", 1, 20, 5)

if st.button("🚀 Crawl and Extract"):
    if not url.startswith("http"):
        st.warning("Please enter a valid URL.")
    else:
        with st.spinner("Crawling pages and extracting content..."):
            pages = crawl_site(url, max_pages=max_pages)
            full_text = " ".join(pages)

            if len(full_text) < 500:
                st.error("❌ Not enough content was extracted.")
            else:
                keywords = extract_keywords(full_text, max_phrases=50)
                results = []
                for phrase in keywords:
                    results.append({
                        "Keyword": phrase,
                        "Intent": detect_intent(phrase),
                        "Source": url
                    })

                df = pd.DataFrame(results)
                st.success(f"✅ Extracted {len(df)} keyword suggestions from {len(pages)} pages.")
                st.dataframe(df)

                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download CSV", csv, "longtail_keywords.csv", "text/csv")
