from flask import Flask, request, jsonify, render_template, redirect, session
from supabase import create_client, Client
from openai import OpenAI
from dotenv import load_dotenv
import stripe
import os
from datetime import datetime, timedelta
from functools import wraps
import jwt

# Load environment variables FIRST
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or os.getenv(
    "APP_SECRET") or "dev-secret"

JWT_SECRET = os.getenv("JWT_SECRET")


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "Missing token"}), 401

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(
                token,
                app.secret_key,
                algorithms=["HS256"]
            )
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401

        db = SessionLocal()
        user = db.query(User).filter(User.email == payload["email"]).first()
        db.close()

        if not user:
            return jsonify({"error": "User not found"}), 401

        return f(user, *args, **kwargs)

    return decorated

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE")

# Validate Supabase credentials
if not SUPABASE_URL or not SUPABASE_KEY:
    print("[WARNING] Supabase credentials not fully configured")
    print(f"  SUPABASE_URL: {'✓' if SUPABASE_URL else '✗'}")
    print(f"  SUPABASE_KEY: {'✓' if SUPABASE_KEY else '✗'}")
    # Use dummy values for now (app will still initialize but auth/DB will fail gracefully)
    SUPABASE_URL = SUPABASE_URL or "https://placeholder.supabase.co"
    SUPABASE_KEY = SUPABASE_KEY or "placeholder-key"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"[WARNING] Failed to initialize Supabase client: {str(e)}")
    supabase = None

# STRIPE CONFIG
stripe.api_key = os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY")
YOUR_DOMAIN = os.getenv("DOMAIN_URL", "http://127.0.0.1:5000")

# =========================
# TIER DEFINITIONS (SOURCE OF TRUTH)
# =========================
TIERS = {
    "free": {
        "limit": 1,
        "can_save": False,
        "can_rerun": False,
        "priority": "low"
    },
    "pro": {
        "limit": 20,
        "can_save": True,
        "can_rerun": True,
        "priority": "high"
    },
    "agency": {
        "limit": 200,
        "can_save": True,
        "can_rerun": True,
        "priority": "highest"
    }
}
def tier_allows(user, capability):
    tier = user.tier
    return TIERS.get(tier, {}).get(capability, False)

# OPENAI CLIENT
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


print("[INFO] App initialized successfully")
# Helper: normalize different Supabase sign-in responses
def _parse_supabase_signin_result(result):
    """Return tuple (email, id, error_or_none).
    Accepts different shapes returned by supabase client (dict, object-like).
    """
    email = None
    user_id = None
    err = None

    try:
        # If dict-like
        if isinstance(result, dict):
            err = result.get("error")
            data = result.get("data") or result.get("user") or result.get("session")
            # If data is a dict with user
            if isinstance(data, dict) and data.get("user"):
                u = data.get("user")
                if isinstance(u, dict):
                    email = u.get("email")
                    user_id = u.get("id")
                else:
                    email = getattr(u, "email", None)
                    user_id = getattr(u, "id", None)
            # If data itself is user-like
            elif isinstance(data, dict) and data.get("email"):
                email = data.get("email")
                user_id = data.get("id")
            # direct user at top-level
            elif isinstance(result.get("user"), dict):
                email = result.get("user").get("email")
                user_id = result.get("user").get("id")
            else:
                # fallback: check common keys
                email = result.get("email") or (data.get("email") if isinstance(data, dict) else None)
                user_id = result.get("id") or (data.get("id") if isinstance(data, dict) else None)

        else:
            # object-like: try attributes
            err = getattr(result, "error", None)
            data = getattr(result, "data", None) or getattr(result, "user", None) or getattr(result, "session", None)
            if data:
                if isinstance(data, dict):
                    email = data.get("email") or (data.get("user") and data.get("user").get("email"))
                    user_id = data.get("id") or (data.get("user") and data.get("user").get("id"))
                else:
                    email = getattr(data, "email", None) or (getattr(data, "user", None) and getattr(getattr(data, "user", None), "email", None))
                    user_id = getattr(data, "id", None) or (getattr(data, "user", None) and getattr(getattr(data, "user", None), "id", None))
            # last-ditch: attributes on result
            email = email or getattr(result, "email", None)
            user_id = user_id or getattr(result, "id", None)

    except Exception as e:
        # Return what we managed and the exception as error
        return (email, user_id, f"parse-error: {str(e)}")

    return (email, user_id, err)

# --------------------
# LANDING PAGE
# --------------------


@app.route("/")
def landing():
    return render_template("landing.html")

# --------------------
# HOME PAGE (Dashboard)
# --------------------


@app.route("/home")
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
                # your Stripe monthly price ID
                "price": os.getenv("STRIPE_PRICE_ID"),
                "quantity": 1,
            }],
            success_url=YOUR_DOMAIN +
            "/success?session_id={CHECKOUT_SESSION_ID}",
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

# ============================================
# USER AUTHENTICATION (Supabase)
# ============================================

# SIGNUP PAGE


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        try:
            email = request.form.get("email")
            password = request.form.get("password")

            # Validate input
            if not email or not password:
                return render_template("signup.html", error="Email and password are required.")
            if len(password) < 6:
                return render_template("signup.html", error="Password must be at least 6 characters.")

            # Check if Supabase is available
            if not supabase:
                return render_template("signup.html", error="Authentication service not configured. Please contact support.")

            response = supabase.auth.sign_up({
    "email": email,
    "password": password,
    "options": {
        "email_redirect_to": "https://aiassistantpros.onrender.com/login"
    }
})

            # Normalize response (dict or object)
            error = None
            user_id = None
            if isinstance(response, dict):
                error = response.get("error")
                user = response.get("user")
                if user:
                    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
            else:
                error = getattr(response, "error", None)
                user = getattr(response, "user", None)
                if user:
                    user_id = getattr(user, "id", None)

            if error:
                if isinstance(error, dict) and error.get("message"):
                    error_msg = error.get("message")
                else:
                    error_msg = str(error)
                return render_template("signup.html", error=error_msg)
            else:
                # Create user profile in database as FREE tier with 3-day trial by default
                if user_id:
                    try:
                        trial_ends_at = (datetime.utcnow() + timedelta(days=3)).isoformat()
                        supabase.table("users").insert({
                            "id": user_id,
                            "email": email,
                            "tier": "free",
                            "trial_ends_at": trial_ends_at,
                            "created_at": "now()"
                        }).execute()
                    except Exception as db_error:
                        print(f"[WARNING] Could not create user profile: {str(db_error)}")
                        # Continue anyway - profile will be created on first login
                
                return redirect("/signup-success")
        except Exception as e:
            error_msg = f"Signup error: {str(e)}"
            print(f"[ERROR] Signup route exception: {error_msg}")
            return render_template("signup.html", error="An error occurred during signup. Please try again.")

    # Handles GET requests — user opening page normally
    return render_template("signup.html")


# LOGIN PAGE
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            return render_template("login.html", error="Email and password are required.")

        try:
            result = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            # Extract user info safely
            session_data = result.session
            user = result.user

            if session_data is None:
                return render_template("login.html", error="Authentication failed. Check your credentials.")

            # Fallback: if result.user is None, use data from session
            if user is None:
                user = session_data.user

            if user is None:
                return render_template("login.html", error="Authentication failed. Could not load user data.")

            # Store essentials in session
            session["user"] = {
                "id": user.id,
                "email": user.email,
                "tier": "free",
                "trial_ends_at": None
            }

            return redirect("/dashboard")

        except Exception as e:
            print("LOGIN ERROR:", e)
            return render_template("login.html", error="Login failed. Please try again.")

    return render_template("login.html")
 

           
      
                                  
@app.route("/signup-success")
def signup_success():
    return render_template("signup_success.html")

# LOGOUT


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")


# (dashboard handler is defined later with consistent session handling)

# CAPTION PAGE (Free Tier)
@app.route("/caption")
def caption():
    return render_template("caption.html")


@app.route("/generate", methods=["POST"])
@token_required
def generate(user):
    tier = user.tier
    limit = TIERS.get(tier, {}).get("limit", 0)   

    # FREE = preview only (hard stop)
    if tier == "free" and user.used >= 1:
        return jsonify({
             "error": "Free preview already used",
             "upgrade": True
        }), 403

    # PAID TIERS = usage limits
    if user.used >= limit:
        return jsonify({
        "error": "Usage limit reached",
        "upgrade": True
    }), 403

    # CONSUME USE IMMEDIATELY

    user.used += 1
    db = SessionLocal()
    db.merge(user)
    db.commit()
    db.close()

    prompt = request.json.get("prompt")
    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    response = client.chat.completions.create(
        model=TIERS[tier]["model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return jsonify({
        "tier": tier,
        "used": user.used,
        "limit": limit,
        "output": response.choices[0].message.content
    })


# ==========================
# PREMIUM DASHBOARD
# ==========================

@app.route("/dashboard")
def dashboard():
    try:
        if "user" not in session:
            return redirect("/login")

        user = session.get("user") or {}
        user_email = user.get("email")
        user_tier = user.get("tier", "free")
        trial_ends_at = user.get("trial_ends_at")

        # Calculate days left
        trial_days_left = None
        if trial_ends_at and user_tier == "free":
            try:
                trial_end = datetime.fromisoformat(trial_ends_at)
                days_left = (trial_end - datetime.utcnow()).days
                trial_days_left = max(0, days_left + 1)
            except:
                print("[WARNING] Could not calculate trial days")

        return render_template(
            "dashboard_unified.html",
            user_email=user_email,
            user_tier=user_tier,
            trial_days_left=trial_days_left
        )

    except Exception as e:
        print("[ERROR] Dashboard exception:", e)
        return render_template("login.html", error="An error occurred. Please log in again.")
# Helper to check if user is premium or has active trial
def is_premium():
    if "user" not in session:
        return False
    user = session.get("user") or {}
    
    # Check if user is premium subscriber
    tier = user.get("tier", "free") if isinstance(user, dict) else "free"
    if tier == "premium":
        return True
    
    # Check if user has active trial
    trial_ends_at = user.get("trial_ends_at") if isinstance(user, dict) else None
    if trial_ends_at:
        try:
            trial_end = datetime.fromisoformat(trial_ends_at)
            if datetime.utcnow() < trial_end:
                return True
        except Exception as e:
            print(f"[WARNING] Could not parse trial_ends_at: {str(e)}")
    
    return False


# Redirect free users to subscribe
@app.route("/subscribe")
def subscribe():
    if "user" not in session:
        return redirect("/login")
    return redirect("/create-checkout-session", code=303)


# ==========================
# ERROR HANDLERS
# ==========================

@app.errorhandler(500)
def internal_error(error):
    print(f"[ERROR] 500 Internal Server Error: {str(error)}")
    return render_template("500.html", error=str(error)), 500


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


# ==========================
# PREMIUM AI ENDPOINTS
# ==========================











# =====================================================
# RUN THE APP
# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)