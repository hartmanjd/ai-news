# news.py
# ------------------------------------------------------------
# What this script does, in order:
#   1. Finds today's most popular AI stories (Hacker News + news sites)
#   2. Downloads the text of each article
#   3. Asks an LLM (DeepSeek) to write a one-paragraph summary
#   4. Builds a clean web page in the "docs" folder
#
# Run it with:   python news.py
# ------------------------------------------------------------

import os
import re
import time
import html
import calendar
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import feedparser
import trafilatura
from dotenv import load_dotenv

# Load secrets (like your API key) from a file called .env, if it exists.
# On GitHub, the secrets come from the repo settings instead.
load_dotenv()


# ============================================================
# SETTINGS - change these to taste
# ============================================================

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-flash"      # cheap + fast. "deepseek-v4-pro" is smarter but costs more.

MAX_HACKER_NEWS_STORIES = 6            # top AI stories by upvotes
MAX_STORIES_PER_SITE = 2               # newest stories from each news site
MIN_HACKER_NEWS_POINTS = 30            # ignore stories with fewer upvotes than this

TIMEZONE = "America/Los_Angeles"
OUTPUT_FOLDER = "docs"                 # GitHub Pages serves the website from this folder

# News sites that have an AI-only RSS feed
NEWS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica": "https://arstechnica.com/ai/feed/",
    "MIT Technology Review": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
}

# A Hacker News title counts as "AI news" if it contains one of these words...
AI_WORDS = [
    "ai", "llm", "llms", "gpt", "chatgpt", "openai", "anthropic", "claude",
    "gemini", "deepmind", "deepseek", "llama", "mistral", "copilot", "agi",
    "qwen", "grok", "transformer", "transformers", "diffusion",
]
# ...or one of these phrases
AI_PHRASES = [
    "artificial intelligence", "machine learning", "neural network",
    "language model", "deep learning",
]

# Skip ads and event promos that sometimes show up in news feeds
SKIP_IF_TITLE_HAS = ["% off", "ticket", "sponsored", "webinar", "disrupt 20"]

# Pretend to be a normal browser so websites don't block us
HEADERS = {"User-Agent": "Mozilla/5.0 (AI News Digest; personal project)"}


# ============================================================
# STEP 1: Find stories
# ============================================================

def is_about_ai(title):
    """Returns True if a headline looks like it's about AI."""
    title_lower = title.lower()

    # Split the title into words:  "OpenAI's GPT-5 is here" -> ["openai", "s", "gpt", "5", "is", "here"]
    words = re.findall(r"\w+", title_lower)

    for word in AI_WORDS:
        if word in words:
            return True

    for phrase in AI_PHRASES:
        if phrase in title_lower:
            return True

    return False


def looks_like_an_ad(title):
    """Returns True if a headline looks like a promo instead of news."""
    title_lower = title.lower()
    for bad_text in SKIP_IF_TITLE_HAS:
        if bad_text in title_lower:
            return True
    return False


def get_hacker_news_stories():
    """Gets the most upvoted AI stories from Hacker News in the last 24 hours."""
    print("Checking Hacker News...")

    one_day_ago = int(time.time()) - 24 * 60 * 60

    # The Hacker News search API. An empty query returns stories ranked by upvotes.
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "tags": "story",
        "numericFilters": f"created_at_i>{one_day_ago},points>{MIN_HACKER_NEWS_POINTS}",
        "hitsPerPage": 300,
    }

    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    results = response.json()["hits"]

    stories = []
    for item in results:
        title = item.get("title") or ""
        link = item.get("url")

        # Skip "Ask HN" posts (no outside link) and anything not about AI
        if not link:
            continue
        if not is_about_ai(title):
            continue

        stories.append({
            "title": title,
            "link": link,
            "source": "Hacker News",
            "points": item.get("points", 0),
            "comments": item.get("num_comments", 0),
            "discussion_link": "https://news.ycombinator.com/item?id=" + item["objectID"],
            "feed_summary": "",   # Hacker News doesn't give us a summary
        })

    # Most upvoted first
    stories.sort(key=lambda story: story["points"], reverse=True)

    print(f"  found {len(stories)} AI stories, keeping the top {MAX_HACKER_NEWS_STORIES}")
    return stories[:MAX_HACKER_NEWS_STORIES]


def get_news_site_stories(site_name, feed_url):
    """Gets the newest stories (from the last 24 hours) from one news site's RSS feed."""
    print(f"Checking {site_name}...")

    response = requests.get(feed_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    feed = feedparser.parse(response.content)

    one_day_ago = time.time() - 24 * 60 * 60

    stories = []
    for entry in feed.entries:
        title = entry.get("title", "")

        # When was it published? (feedparser gives us a UTC time tuple,
        # calendar.timegm turns it into seconds so we can compare it)
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published is None:
            continue
        published_seconds = calendar.timegm(published)
        if published_seconds < one_day_ago:
            continue

        if looks_like_an_ad(title):
            continue

        stories.append({
            "title": title,
            "link": entry.get("link", ""),
            "source": site_name,
            "points": None,
            "comments": None,
            "discussion_link": None,
            "feed_summary": remove_html_tags(entry.get("summary", "")),
        })

        if len(stories) == MAX_STORIES_PER_SITE:
            break

    print(f"  found {len(stories)}")
    return stories


def remove_html_tags(text):
    """Turns '<p>Hello <b>world</b></p>' into 'Hello world'."""
    no_tags = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(" ".join(no_tags.split()))


def find_all_stories():
    """Collects stories from every source and removes duplicates."""
    all_stories = []

    # Each source is wrapped in try/except so one broken site doesn't stop the whole app
    try:
        all_stories = all_stories + get_hacker_news_stories()
    except Exception as error:
        print(f"  Hacker News failed: {error}")

    for site_name, feed_url in NEWS_FEEDS.items():
        try:
            all_stories = all_stories + get_news_site_stories(site_name, feed_url)
        except Exception as error:
            print(f"  {site_name} failed: {error}")

    # Remove duplicates (the same link showing up twice)
    unique_stories = []
    links_seen = []
    for story in all_stories:
        clean_link = story["link"].split("?")[0].rstrip("/")
        if clean_link in links_seen:
            continue
        links_seen.append(clean_link)
        unique_stories.append(story)

    return unique_stories


# ============================================================
# STEP 2: Download each article's text
# ============================================================

def get_article_text(story):
    """Downloads the article and pulls out just the main text (no menus or ads)."""
    try:
        page = trafilatura.fetch_url(story["link"])
        if page:
            text = trafilatura.extract(page)
            if text and len(text) > 300:
                return text[:8000]   # the first 8000 characters is plenty for a summary
    except Exception as error:
        print(f"  couldn't download article: {error}")

    # Backup plan: use the short summary from the RSS feed, if it's long enough
    if len(story["feed_summary"]) > 200:
        return story["feed_summary"]

    return None


# ============================================================
# STEP 3: Summarize with the LLM
# ============================================================

def summarize(title, article_text):
    """Sends the article to DeepSeek and gets back a one-paragraph summary."""

    # No API key? Use the first few sentences of the article so you can still test the app.
    if not DEEPSEEK_API_KEY:
        sentences = article_text.replace("\n", " ").split(". ")
        return ". ".join(sentences[:3]).strip() + "."

    instructions = (
        "You summarize news articles for a busy reader who follows AI. "
        "Write ONE paragraph of 4 to 6 sentences in plain, simple English. "
        "Say what happened, who is involved, and why it matters. "
        "Only use facts from the article. No hype, no bullet points, no heading."
    )

    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": f"Headline: {title}\n\nArticle:\n{article_text}"},
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
            # DeepSeek "thinks" before answering by default. That thinking uses up
            # max_tokens, which can leave the summary cut off or empty.
            # A summary doesn't need deep thinking, so we turn it off (also faster + cheaper).
            "thinking": {"type": "disabled"},
        },
        timeout=120,
    )
    response.raise_for_status()
    answer = response.json()["choices"][0]["message"]["content"]
    answer = answer.strip()

    # Safety check: never put an empty summary on the page
    if answer == "":
        raise Exception("DeepSeek sent back an empty summary")

    return answer


# ============================================================
# STEP 4: Build the web page
# ============================================================

def make_story_card(number, story):
    """Returns the HTML for one story."""
    # html.escape() makes text safe to put in a web page (e.g. turns < into &lt;)
    title = html.escape(story["title"])
    link = html.escape(story["link"], quote=True)
    summary = html.escape(story["summary"])
    source = html.escape(story["source"])

    # The little line under the summary: popularity (Hacker News only) + links
    extras = ""
    if story["points"] is not None:
        discussion = html.escape(story["discussion_link"], quote=True)
        extras = (
            f'<span>▲ {story["points"]} points</span>'
            f'<a href="{discussion}" target="_blank" rel="noopener">{story["comments"]} comments</a>'
        )

    return f"""
    <article class="story">
      <div class="story-top">
        <span class="number">{number:02d}</span>
        <span class="source">{source}</span>
      </div>
      <h2><a href="{link}" target="_blank" rel="noopener">{title}</a></h2>
      <p>{summary}</p>
      <div class="meta">
        {extras}
        <a class="read" href="{link}" target="_blank" rel="noopener">Read the full article →</a>
      </div>
    </article>"""


def make_page(page_title, date_text, stories, past_days):
    """Returns the HTML for a whole page."""
    cards = ""
    for number, story in enumerate(stories, start=1):
        cards = cards + make_story_card(number, story)

    if not stories:
        cards = '<p class="empty">No stories could be loaded today. Check the GitHub Actions log.</p>'

    past_links = ""
    for day in past_days:
        past_links = past_links + f'<li><a href="{day}.html">{day}</a></li>'

    past_section = ""
    if past_links:
        past_section = f'<section class="past"><h3>Past days</h3><ul>{past_links}</ul></section>'

    with open("page_style.css", encoding="utf-8") as css_file:
        css = css_file.read()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  <style>{css}</style>
</head>
<body>
  <main>
    <header>
      <p class="kicker">AI Daily</p>
      <h1>{html.escape(date_text)}</h1>
      <p class="subtitle">{len(stories)} stories, summarized. Tap a headline for the full article.</p>
    </header>
    {cards}
    <nav class="bottom"><a href="index.html">Latest</a></nav>
    {past_section}
  </main>
</body>
</html>"""


def save_file(path, text):
    with open(path, "w", encoding="utf-8") as file:
        file.write(text)


# ============================================================
# RUN EVERYTHING
# ============================================================

def main():
    now = datetime.now(ZoneInfo(TIMEZONE))
    today = now.strftime("%Y-%m-%d")                 # e.g. 2026-09-24  (used for the file name)
    pretty_date = now.strftime("%A, %B %d, %Y")      # e.g. Thursday, September 24, 2026

    if not DEEPSEEK_API_KEY:
        print("NOTE: no DEEPSEEK_API_KEY found, so summaries will just be the first few sentences.\n")

    # Step 1
    stories = find_all_stories()
    print(f"\n{len(stories)} stories to summarize.\n")

    # Steps 2 and 3
    finished_stories = []
    for story in stories:
        print(f"Summarizing: {story['title']}")

        article_text = get_article_text(story)
        if article_text is None:
            print("  skipped (couldn't read the article)")
            continue

        try:
            story["summary"] = summarize(story["title"], article_text)
        except Exception as error:
            print(f"  skipped (LLM error: {error})")
            continue

        finished_stories.append(story)

    # Step 4
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # Find the past days' pages that already exist (e.g. "2026-09-23.html")
    past_days = []
    for file_name in os.listdir(OUTPUT_FOLDER):
        if re.match(r"\d{4}-\d{2}-\d{2}\.html$", file_name):
            day = file_name.replace(".html", "")
            if day != today:
                past_days.append(day)
    past_days.sort(reverse=True)     # newest first
    past_days = past_days[:30]       # only list the last 30 days

    page = make_page(f"AI Daily — {pretty_date}", pretty_date, finished_stories, past_days)

    save_file(os.path.join(OUTPUT_FOLDER, f"{today}.html"), page)   # today's permanent page
    save_file(os.path.join(OUTPUT_FOLDER, "index.html"), page)       # "latest" page

    print(f"\nDone! Saved {len(finished_stories)} stories to {OUTPUT_FOLDER}/{today}.html")


if __name__ == "__main__":
    main()
