import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI
from twilio.rest import Client as TwilioClient

app = Flask(__name__)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

BUSINESS_NAME = "SmartPro Window & Gutter Cleaning LLC"
BUSINESS_PHONE = "970-716-0591"
SERVICE_AREA = "Parker, Elizabeth, Aurora, Centennial & surrounding areas"

RATE_INOUT_DOUBLE = 30
RATE_INOUT_SINGLE = 15
RATE_EXT_SCREENS_DOUBLE = 20
RATE_EXT_SCREENS_SINGLE = 10
RATE_EXT_NOSCREENS_DOUBLE = 18
RATE_EXT_NOSCREENS_SINGLE = 9

GUTTER_1_STORY_BASE = 199
GUTTER_1_STORY_BUNDLE = 249
GUTTER_2_STORY_BASE = 299
GUTTER_2_STORY_BUNDLE = 349
GUTTER_DOWNSPOUT_STANDARD = 25
LARGE_HOME_SQFT_THRESHOLD = 3600

WINDOW_GUIDE = (
    "How We Count Windows:\n"
    "- A double-pane window has two separate glass sections (like a double-hung or slider).\n"
    "- A single-pane window is one solid piece of glass with no dividing sash.\n"
    "- Decorative grids glued on top of the glass do not count as extra panes.\n"
    "- Not sure? Send a photo and we will count them for you at no charge."
)

def send_email(to_email, subject, body):
    api_key = os.environ["BREVO_API_KEY"]
    sender_email = os.environ["SENDER_EMAIL"]
    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "sender": {"email": sender_email, "name": "SmartPro Window & Gutter Cleaning"},
            "to": [{"email": to_email}],
            "subject": subject,
            "textContent": body,
        },
        timeout=30,
    )
    response.raise_for_status()

def send_sms(to_phone, body):
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    from_number = os.environ["TWILIO_PHONE_NUMBER"]
    twilio_client = TwilioClient(account_sid, auth_token)
    max_length = 1500
    text = body if len(body) <= max_length else body[:max_length] + "... (see email for full quote)"
    twilio_client.messages.create(body=text, from_=from_number, to=to_phone)

def normalize_phone(raw_phone):
    digits = "".join(ch for ch in raw_phone if ch.isdigit())
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(force=True)
    data = payload.get("submission", payload)

    client_name = data.get("name", "Customer")
    address = data.get("address", "")
    client_phone_raw = data.get("phone", "")
    client_email = data.get("email", "")

    double_count = int(data.get("double_pane_count", 0) or 0)
    single_count = int(data.get("single_pane_count", 0) or 0)

    want_gutter = str(data.get("want_gutter", "no")).lower() in ("yes", "y", "true")
    gutter_stories = str(data.get("gutter_stories", "1"))
    gutter_sqft = int(data.get("gutter_sqft", 0) or 0)
    clogged_downspouts = int(data.get("clogged_downspouts", 0) or 0)
    possible_snake_work = str(data.get("possible_snake_work", "no")).lower() in ("yes", "y", "true")
    underground_drainage = str(data.get("underground_drainage", "no")).lower() in ("yes", "y", "true")

    post_construction = str(data.get("post_construction", "no")).lower() in ("yes", "y", "true")
    overspray = str(data.get("overspray", "no")).lower() in ("yes", "y", "true")
    silicone = str(data.get("silicone", "no")).lower() in ("yes", "y", "true")
    notes = data.get("notes", "")

    option_1_price = (double_count * RATE_INOUT_DOUBLE) + (single_count * RATE_INOUT_SINGLE)
    option_2_price = (double_count * RATE_EXT_SCREENS_DOUBLE) + (single_count * RATE_EXT_SCREENS_SINGLE)
    option_3_price = (double_count * RATE_EXT_NOSCREENS_DOUBLE) + (single_count * RATE_EXT_NOSCREENS_SINGLE)

    window_options_text = (
        "Option 1: Interior/Exterior window cleaning (screens/tracks always included) - $" + str(option_1_price) + "\n"
        "Option 2: Exterior window cleaning only with screens - $" + str(option_2_price) + "\n"
        "Option 3: Exterior window cleaning only, no screens - $" + str(option_3_price)
    )

    gutter_text = "Not requested."
    gutter_needs_assessment = False

    if want_gutter:
        if gutter_stories == "2" and gutter_sqft >= LARGE_HOME_SQFT_THRESHOLD:
            gutter_needs_assessment = True
            gutter_text = (
                "This 2-story home is " + str(gutter_sqft) + " sq ft, which is above our "
                + str(LARGE_HOME_SQFT_THRESHOLD) + " sq ft threshold for instant online pricing. "
                "An in-person assessment is required for an accurate gutter cleaning quote."
            )
        else:
            base_price = GUTTER_2_STORY_BASE if gutter_stories == "2" else GUTTER_1_STORY_BASE
            bundle_price = GUTTER_2_STORY_BUNDLE if gutter_stories == "2" else GUTTER_1_STORY_BUNDLE
            per_downspout_total = clogged_downspouts * GUTTER_DOWNSPOUT_STANDARD
            pay_per_downspout_total = base_price + per_downspout_total

            gutter_text = (
                "Gutter Cleaning (" + gutter_stories + "-story house):\n"
                "Option A - Base cleaning + $" + str(GUTTER_DOWNSPOUT_STANDARD) + " per clogged downspout ("
                + str(clogged_downspouts) + " reported): $" + str(pay_per_downspout_total) + "\n"
                "Option B - Flat-rate bundle (cleaning + any standard clogged downspouts included): $" + str(bundle_price)
            )

            if possible_snake_work:
                gutter_text += (
                    "\n\nNote: One or more downspouts may require snaking or disassembly beyond a standard flush. "
                    "This will be assessed on-site and reported to you for approval before any extra work or "
                    "additional charge is applied."
                )

    underground_text = ""
    if underground_drainage:
        underground_text = (
            "\n\nUnderground drainage work was noted for this property. This is quoted separately "
            "from standard gutter cleaning and requires an on-site assessment."
        )

    conditions = []
    if post_construction:
        conditions.append("post-construction debris")
    if overspray:
        conditions.append("paint/stucco overspray")
    if silicone:
        conditions.append("silicone or caulking residue")
    conditions_text = ", ".join(conditions) if conditions else "None"

    prompt = (
        "Write a professional, concise, copy-paste-ready customer quote in plain text.\n\n"
        "Business:\n" + BUSINESS_NAME + "\n"
        "Call or Text Omar: " + BUSINESS_PHONE + "\n"
        "Service area: " + SERVICE_AREA + "\n\n"
        "Customer:\n"
        "Name: " + client_name + "\n"
        "Service address: " + address + "\n"
        "Customer phone: " + (client_phone_raw or "Not included") + "\n"
        "Double-pane windows: " + str(double_count) + "\n"
        "Single-pane windows: " + str(single_count) + "\n\n"
        "Window options (use exact prices given):\n" + window_options_text + "\n\n"
        "Gutter cleaning add-on:\n" + gutter_text + underground_text + "\n\n"
        "Special job conditions present: " + conditions_text + "\n\n"
        "Window counting reference (include near the end, titled 'How We Count Windows'):\n"
        + WINDOW_GUIDE + "\n\n"
        "Additional notes:\n" + (notes or "None") + "\n\n"
        "Rules:\n"
        "- Use only the prices supplied above. Never invent or change prices.\n"
        "- Start with the business name, then Client and Service Address.\n"
        "- List the three window options clearly. Mention screens/tracks are always included in Option 1.\n"
        "- If gutter cleaning was requested and needs in-person assessment, clearly state that and do not show a price.\n"
        "- If gutter cleaning has normal pricing, present Option A and Option B clearly so the client can choose, "
        "and briefly note that Option B is the better deal if there is more than one clogged downspout.\n"
        "- If snake work or disassembly was flagged, include that note exactly as given, making clear this is "
        "assessed on-site and reported for the client's approval before any extra charge applies.\n"
        "- If underground drainage was flagged, include that note exactly as given.\n"
        "- If special conditions are present, add a short professional note that extra labor/time applies and will "
        "be billed after an on-site inspection. Do not invent a dollar amount for this.\n"
        "- If no special conditions are present, omit that note entirely.\n"
        "- Include the window counting section near the end, reworded naturally.\n"
        "- End with: Reply with your preferred option and the date that works best for you.\n"
        "- Then end with: Call or Text Omar: 970-716-0591\n"
        "- Friendly, professional, neighborly, and not pushy. No emojis, no markdown tables.\n"
    )

    response = client.responses.create(model="gpt-4.1-mini", input=prompt)
    quote = response.output_text.strip()

    delivery_status = {"email": False, "sms": False}

    if client_email:
        try:
            send_email(client_email, "Your SmartPro Window & Gutter Cleaning Quote", quote)
            delivery_status["email"] = True
        except Exception as e:
            print("Email send failed: " + str(e))

    normalized_phone = normalize_phone(client_phone_raw) if client_phone_raw else None
    if normalized_phone:
        try:
            send_sms(normalized_phone, quote)
            delivery_status["sms"] = True
        except Exception as e:
            print("SMS send failed: " + str(e))

    notify_address = os.environ.get("OWNER_EMAIL")
    if notify_address:
        try:
            send_email(notify_address, "New Lead: " + client_name, quote)
        except Exception as e:
            print("Owner notify email failed: " + str(e))

    return jsonify({"status": "ok", "quote": quote, "delivery": delivery_status, "needs_assessment": gutter_needs_assessment})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

import os
from openai import OpenAI
from twilio.rest import Client as TwilioClient

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

twilio_client = TwilioClient(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN"),
)
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")

def send_sms(to: str, body: str):
    if not to or not body:
        return
    twilio_client.messages.create(
        to=to,
        from_=TWILIO_NUMBER,
        body=body,
    )

def generate_quote_text(prompt: str) -> str:
    response = openai_client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )
    return response.output_text


@app.route("/sms-quote", methods=["POST"])
def sms_quote():
    data = request.get_json() or {}

    customer_phone = data.get("phone")
    prompt = data.get("prompt") or "SmartPro window and gutter cleaning quote request."

    quote_text = generate_quote_text(prompt)

    if customer_phone:
        send_sms(customer_phone, quote_text)

    return {"quote": quote_text}
