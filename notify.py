# notify.py
# ------------------------------------------------------------
# Sends today's link to your phone.
#   - Push notification with ntfy (free)  -> needs NTFY_TOPIC
#   - Text message with Twilio (paid)     -> needs the TWILIO_ settings
# If a setting is missing, that method is simply skipped.
#
# Run it with:   python notify.py
# ------------------------------------------------------------

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()

TIMEZONE = "America/Los_Angeles"

# The website address, e.g. https://yourname.github.io/ai-news/
PAGE_BASE_URL = os.getenv("PAGE_BASE_URL", "")

# ntfy: the "topic" is like a private channel name. Pick something hard to guess.
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")

# Twilio (optional)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")    # your Twilio number, e.g. +19165551234
TWILIO_TO_NUMBERS = os.getenv("TWILIO_TO_NUMBERS", "")      # one or more, separated by commas


def send_push(link, message):
    print("Sending push notification with ntfy...")
    response = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": "AI Daily",
            "Click": link,          # tapping the notification opens this link
            "Tags": "newspaper",    # shows a 📰 icon
        },
        timeout=30,
    )
    response.raise_for_status()
    print("  sent!")


def send_texts(link, message):
    # Turn "+1916..., +1530..." into a list: ["+1916...", "+1530..."]
    phone_numbers = []
    for number in TWILIO_TO_NUMBERS.split(","):
        number = number.strip()
        if number:
            phone_numbers.append(number)

    twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

    for number in phone_numbers:
        print(f"Texting {number}...")
        response = requests.post(
            twilio_url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={
                "From": TWILIO_FROM_NUMBER,
                "To": number,
                "Body": f"{message} {link}",
            },
            timeout=30,
        )
        if response.status_code >= 400:
            print(f"  failed: {response.text}")
        else:
            print("  sent!")


def main():
    if not PAGE_BASE_URL:
        print("No PAGE_BASE_URL set, so there's no link to send.")
        return

    today = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")

    # Make sure the base address ends with "/" before adding the file name
    base = PAGE_BASE_URL
    if not base.endswith("/"):
        base = base + "/"
    link = base + today + ".html"

    message = "Today's AI news is ready."
    print(f"Link: {link}")

    if NTFY_TOPIC:
        send_push(link, message)
    else:
        print("No NTFY_TOPIC set, skipping push notification.")

    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER and TWILIO_TO_NUMBERS:
        send_texts(link, message)
    else:
        print("Twilio isn't set up, skipping text messages.")


if __name__ == "__main__":
    main()
