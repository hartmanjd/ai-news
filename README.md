# AI Daily

Every morning this app:

1. Finds the most popular AI stories from the last 24 hours. It pulls the most-upvoted AI posts on Hacker News plus the newest stories from TechCrunch, The Verge, Ars Technica and MIT Technology Review.
2. Downloads each article and has DeepSeek write a one-paragraph summary.
3. Builds a clean web page with the headlines, summaries and links.
4. Sends the page's link to your phone.

It runs for free on GitHub, so your computer can stay off.

## The files

| File | What it does |
|---|---|
| `news.py` | Steps 1–3: finds stories, summarizes them, builds the page into `docs/` |
| `notify.py` | Step 4: sends the link (push notification and/or text message) |
| `page_style.css` | How the page looks |
| `.github/workflows/daily.yml` | Tells GitHub to run everything every morning |
| `requirements.txt` | Python packages the app needs |
| `.env.example` | Template for your secret keys when running on your own PC |

---

## Setup (about 15 minutes, one time)

### 1. Put the code on GitHub

1. Make a free account at github.com if you don't have one.
2. Click **+** (top right) → **New repository**. Name it `ai-news`, set it to **Public** (free GitHub Pages needs a public repo), and click **Create repository**.
3. On the new repo's page, click **uploading an existing file**. Drag in everything from this folder **except** a `.env` file if you've made one.
   - The `.github` folder starts with a dot, so Windows Explorer may hide it. If it doesn't upload, click **Add file → Create new file**, type `.github/workflows/daily.yml` as the name, and paste in the contents of that file.
4. Click **Commit changes**.

### 2. Turn on the website

Go to repo **Settings → Pages**. Under **Build and deployment → Source**, choose **GitHub Actions**.

### 3. Get the phone app

Install **ntfy** (free) from the App Store or Google Play. Tap **+** and subscribe to a topic name you make up, something hard to guess like `justin-ai-news-7x93k`. Anyone who knows that name can see your notifications, so don't use something obvious.

### 4. Add your secrets

Go to repo **Settings → Secrets and variables → Actions → New repository secret**, and add:

| Name | Value |
|---|---|
| `DEEPSEEK_API_KEY` | your key from platform.deepseek.com |
| `NTFY_TOPIC` | the topic name from step 3 |

### 5. Test it

Go to the **Actions** tab → **Daily AI News** → **Run workflow**. After a few minutes you should get a notification. Tap it to open the page.

From now on it runs by itself every morning around 7am Pacific.

---

## Adding real text messages later (Twilio)

1. Sign up at twilio.com and buy a phone number. A toll-free number is about $2/month.
2. Complete **Toll-Free Verification** in the Twilio console. US carriers require it before texts will deliver, and it can take a week or more.
3. Add these secrets the same way as step 4:

| Name | Value |
|---|---|
| `TWILIO_ACCOUNT_SID` | from your Twilio console |
| `TWILIO_AUTH_TOKEN` | from your Twilio console |
| `TWILIO_FROM_NUMBER` | your Twilio number, like `+19165551234` |
| `TWILIO_TO_NUMBERS` | who gets texts, separated by commas: `+19165550001,+15305550002` |

That's all. `notify.py` sends texts automatically once those four secrets exist. Cost is roughly 1.2¢ per text, so about $4.50/month for 12 people plus the number.

---

## Running it on your own computer (optional)

```
pip install -r requirements.txt
python news.py
```

Then open `docs/index.html` in your browser. If you don't set an API key, the "summaries" are just the article's first few sentences, which is handy for testing without spending anything.

To use your API key locally, copy `.env.example`, rename the copy to `.env`, and fill it in.

## Easy things to change

All of these are in the **SETTINGS** section at the top of `news.py`:

- **How many stories:** `MAX_HACKER_NEWS_STORIES`, `MAX_STORIES_PER_SITE`
- **Which sites:** add or remove lines in `NEWS_FEEDS` (any RSS feed works)
- **Smarter summaries:** change `DEEPSEEK_MODEL` to `"deepseek-v4-pro"`
- **Summary style:** edit the `instructions` text inside `summarize()`
- **Delivery time:** change the `cron` line in `.github/workflows/daily.yml`. It's in UTC, so add 7 hours to Pacific time in summer and 8 in winter.
