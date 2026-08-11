import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

BUSINESS_NAME = "SmartPro Window & Gutter Cleaning LLC"
BUSINESS_PHONE = "970-716-0591"
SERVICE_AREA = "Parker, Elizabeth, Aurora, Centennial & surrounding areas"

RATE_IN_OUT_SCREENS = 13
RATE_EXT_SCREENS = 9
RATE_EXT_NO_SCREENS = 8

GUTTER_1_STORY = 199
GUTTER_2_STORY = 299
GUTTER_DOWNSPOUT = 25

PANE_GUIDE = (
    "How We Count Window Panes:\n"
    "- One solid piece of glass = 1 pane, even with decorative grids on top.\n"
    "- If you can feel a raised divider across the glass, that is a separate pane.\n"
    "- Sliding windows and sliding glass doors count as 2 panes.\n"
    "- French-style windows with real dividers: each piece of glass is its own pane.\n"
    "- Not sure? Send a photo and we will count for you at no charge."
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

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(force=True)
    data = payload.get("submission", payload)

    client_name = data.get("name", "Customer")
    address = data.get("address", "")
    client_phone = data.get("phone", "")
    client_email = data.get("email", "")

    pane_count = int(data.get("pane_count", 0) or 0)
    want_gutter = str(data.get("want_gutter", "no")).lower() in ("yes", "y", "true")
    gutter_stories = str(data.get("gutter_stories", "1"))
    clogged_downspouts = int(data.get("clogged_downspouts", 0) or 0)

    post_construction = str(data.get("post_construction", "no")).lower() in ("yes", "y", "true")
    overspray = str(data.get("overspray", "no")).lower() in ("yes", "y", "true")
    silicone = str(data.get("silicone", "no")).lower() in ("yes", "y", "true")
    notes = data.get("notes", "")

    option_1_price = pane_count * RATE_IN_OUT_SCREENS
    option_2_price = pane_count * RATE_EXT_SCREENS
    option_3_price = pane_count * RATE_EXT_NO_SCREENS

    window_options_text = (
        "Option 1: Interior/Exterior window cleaning (screens/tracks included) - $" + str(option_1_price) + "\n"
        "Option 2: Exterior window cleaning only with screens - $" + str(option_2_price) + "\n"
        "Option 3: Exterior window cleaning only no screens - $" + str(option_3_price)
    )

    gutter_text = "Not requested."
    if want_gutter:
        base_gutter = GUTTER_2_STORY if gutter_stories == "2" else GUTTER_1_STORY
        downspout_charge = clogged_downspouts * GUTTER_DOWNSPOUT
        gutter_total = base_gutter + downspout_charge
        gutter_text = (
            "Gutter Cleaning (" + gutter_stories + "-story house): $" + str(base_gutter) + "\n"
            "Clogged downspouts (" + str(clogged_downspouts) + " x $" + str(GUTTER_DOWNSPOUT) + "): $" + str(downspout_charge) + "\n"
            "Gutter Cleaning Total: $" + str(gutter_total)
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
        "Customer phone: " + (client_phone or "Not included") + "\n\n"
        "Window options (use exact prices given, pane count = " + str(pane_count) + "):\n"
        + window_options_text + "\n\n"
        "Gutter cleaning add-on:\n" + gutter_text + "\n\n"
        "Special job conditions present: " + conditions_text + "\n\n"
        "Pane counting reference (include near the end, titled 'How We Count Window Panes'):\n"
        + PANE_GUIDE + "\n\n"
        "Additional notes:\n" + (notes or "None") + "\n\n"
        "Rules:\n"
        "- Use only the prices supplied above. Never invent or change prices.\n"
        "- Start with the business name, then Client and Service Address.\n"
        "- List the three window options clearly.\n"
        "- If gutter cleaning was requested, list it as a clearly separate add-on section with its own subtotal.\n"
        "- If special conditions are present, add a short professional note that extra labor/time applies and will "
        "be billed after an on-site inspection. Do not invent a dollar amount for this.\n"
        "- If no special conditions are present, omit that note entirely.\n"
        "- Include the pane counting section near the end, reworded naturally.\n"
        "- End with: Reply with your preferred option and the date that works best for you.\n"
        "- Then end with: Call or Text Omar: 970-716-0591\n"
        "- Friendly, professional, neighborly, and not pushy. No emojis, no markdown tables.\n"
    )

    response = client.responses.create(model="gpt-4.1-mini", input=prompt)
    quote = response.output_text.strip()

    if client_email:
        send_email(client_email, "Your SmartPro Window & Gutter Cleaning Quote", quote)

    notify_address = os.environ.get("OWNER_EMAIL")
    if notify_address:
        send_email(notify_address, "New Lead: " + client_name, quote)

    return jsonify({"status": "ok", "quote": quote})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
