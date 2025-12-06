import os
from flask import Flask, render_template, request, redirect, jsonify
from openai import OpenAI
import stripe

app = Flask(__name__)

# --------------------
# STRIPE CONFIG
# --------------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
YOUR_DOMAIN = os.getenv("DOMAIN_URL", "http://127.0.0.1:5000")

# --------------------
# OPENAI CLIENT
# --------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --------------------
# HOME PAGE
# --------------------
@app.route("/")
def home():
    return render_template("home.html")

# --------------------
# STRIPE CHECKOUT
# --------------------
@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",  # recurring subscription
            line_items=[{
                "price": os.getenv("STRIPE_PRICE_ID"),  # your Stripe monthly price ID
                "quantity": 1,
            }],
            success_url=YOUR_DOMAIN + "/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=YOUR_DOMAIN + "/cancel",
        )

        return redirect(checkout_session.url, code=303)

    except Exception as e:
        return jsonify(error=str(e)), 403

# --------------------
# SUCCESS PAGE
# --------------------
@app.route("/success")
def success():
    return render_template("success.html")

# --------------------
# CANCEL PAGE
# --------------------
# CANCEL PAGE
@app.route("/cancel")
def cancel():
    return render_template("cancel.html")


# CAPTION PAGE (Free Tier)
@app.route("/caption")
def caption():
    return render_template("caption.html")


# GENERATE CAPTION (Free Tier)
@app.route("/generate-caption", methods=["POST"])
def generate_caption():
    try:
        user_text = request.form.get("user_text", "")

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You create short, catchy Instagram-style captions."},
                {"role": "user", "content": user_text}
            ]
        )

        ai_caption = response.choices[0].message.content
        return jsonify({"caption": ai_caption})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================
# PREMIUM DASHBOARD
# ==========================

@app.route("/dashboard")
def dashboard():
    # In the future this could check if user is actually paid
    return render_template("dashboard.html")


# ==========================
# PREMIUM AI ENDPOINTS
# ==========================

@app.route("/api/premium-caption", methods=["POST"])
def api_premium_caption():
    data = request.get_json() or {}
    description = data.get("description", "")
    platform = data.get("platform", "Instagram")
    tone = data.get("tone", "Fun & playful")

    system = (
        "You are an expert social media copywriter. "
        "Write one short, catchy caption with a consistent voice. "
        "Use no more than 3 emojis and 2–3 relevant hashtags."
    )

    user_prompt = (
        f"Platform: {platform}\n"
        f"Tone: {tone}\n"
        f"Description: {description}\n"
        "Write ONE caption."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,
        )
        caption = response.choices[0].message["content"]
        return jsonify({"caption": caption})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hashtags", methods=["POST"])
def api_hashtags():
    data = request.get_json() or {}
    topic = data.get("topic", "")
    platform = data.get("platform", "")
    size = data.get("size", "")

    system = (
        "You generate niche, effective hashtags that are not spammy. "
        "Output all hashtags in one line separated by spaces."
    )

    user_prompt = (
        f"Topic: {topic}\nPlatform: {platform}\nAccount size: {size}\n"
        "Generate 20 hashtags."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )
        hashtags = response.choices[0].message["content"]
        return jsonify({"hashtags": hashtags})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reel-script", methods=["POST"])
def api_reel_script():
    data = request.get_json() or {}
    goal = data.get("goal", "")

    system = (
        "You are a TikTok/Reel script writer. "
        "Write a concise outline: a hook, 3–5 beats, and a CTA."
    )

    user_prompt = f"Goal: {goal}\nWrite the script outline."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,
        )
        script = response.choices[0].message["content"]
        return jsonify({"script": script})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/post-ideas", methods=["POST"])
def api_post_ideas():
    data = request.get_json() or {}
    niche = data.get("niche", "")

    system = (
        "You generate specific, helpful content ideas for creators. "
        "Mix reels, posts, carousels, and stories. Output 10 ideas."
    )

    user_prompt = f"Niche: {niche}\nGenerate 10 ideas."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )
        ideas = response.choices[0].message["content"]
        return jsonify({"ideas": ideas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500    



# =====================================================
# PREMIUM CAPTION TOOL PAGE
# =====================================================
@app.route("/premium-caption")
def premium_caption():
    return render_template("premium_caption.html")


# =====================================================
# PREMIUM CAPTION GENERATOR (AI CALL)
# =====================================================
@app.route("/generate-premium-caption", methods=["POST"])
def generate_premium_caption():
    try:
        user_text = request.form.get("user_text", "")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": "Write longer, creative Instagram captions with emojis."},
                {"role": "user", "content": user_text}
            ]
        )

        ai_caption = response.choices[0].message.content
        return jsonify({"caption": ai_caption})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
