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
@app.route("/cancel")
def cancel():
    return render_template("cancel.html")

# --------------------
# CAPTI
