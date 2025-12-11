from flask import Flask, render_template, request, redirect, session, jsonify
from supabase import create_client, Client
from openai import OpenAI
from dotenv import load_dotenv
import stripe
import os
from datetime import datetime, timedelta

# Load environment variables FIRST
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or os.getenv(
    "APP_SECRET") or "dev-secret"

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE")

# Validate Supabase credentials
if not SUPABASE_URL or not SUPABASE_KEY:
    print("[WARNING] Supabase credentials not fully configured")
    print(f"  SUPABASE_URL: {'✓' if SUPABASE_URL else '✗'}")
    print(f"  SUPABASE_KEY: {'✓' if SUPABASE_KEY else '✗'}")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# STRIPE CONFIG
stripe.api_key = os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY")
YOUR_DOMAIN = os.getenv("DOMAIN_URL", "http://127.0.0.1:5000")

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

            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_redirect_to": (
                        "https://aiassistantpros.onrender.com/login"
                    )
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
        try:
            email = (request.form.get("email") or "").strip()
            password = request.form.get("password") or ""

            # Basic validation
            if not email or not password:
                return render_template("login.html", error="Email and password are required.")

            # Ensure Supabase is configured
            if not SUPABASE_URL or not SUPABASE_KEY:
                print("[ERROR] Supabase credentials missing when attempting login")
                return render_template("login.html", error="Authentication service unavailable. Please try later.")

            # Attempt login; catch network/SDK errors explicitly
            try:
                result = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
            except Exception as sign_exc:
                print(f"[ERROR] Supabase sign_in exception for {email}: {str(sign_exc)}")
                return render_template("login.html", error="Authentication service error. Please try again later.")

            # Debug: log raw result for troubleshooting
            try:
                print("[DEBUG] Supabase sign_in result type:", type(result))
                print("[DEBUG] Supabase sign_in raw result:", repr(result))
            except Exception as e:
                print(f"[DEBUG] Could not print raw result: {str(e)}")

            # Normalize result into (email, user_id, error)
            parsed_email, parsed_user_id, parsed_error = _parse_supabase_signin_result(result)

            # If parsing returned an explicit error, treat as login failure
            if parsed_error:
                if isinstance(parsed_error, dict) and parsed_error.get("message"):
                    msg = parsed_error.get("message")
                else:
                    msg = str(parsed_error)
                print(f"[INFO] Login failed for {email}: {msg}")
                return render_template("login.html", error=msg)

            # On success, pick parsed values, fall back to form email
            user_email = parsed_email or email
            user_id = parsed_user_id

            # Fetch user tier from database, or create profile if it doesn't exist
            user_tier = "free"
            trial_ends_at = None
            try:
                if user_id:
                    # Try to fetch existing user profile by id
                    try:
                        user_data = supabase.table("users").select("tier,trial_ends_at").eq("id", user_id).execute()
                        if user_data and getattr(user_data, "data", None) and len(user_data.data) > 0:
                            user_tier = user_data.data[0].get("tier", "free")
                            trial_ends_at = user_data.data[0].get("trial_ends_at")
                        else:
                            # Create profile with 3-day trial
                            trial_ends_at = (datetime.utcnow() + timedelta(days=3)).isoformat()
                            supabase.table("users").insert({
                                "id": user_id,
                                "email": user_email,
                                "tier": "free",
                                "trial_ends_at": trial_ends_at,
                                "created_at": "now()"
                            }).execute()
                            user_tier = "free"
                    except Exception as query_error:
                        print(f"[WARNING] Query/insert error for user {user_id}: {str(query_error)}")
                        user_tier = "free"
                        trial_ends_at = (datetime.utcnow() + timedelta(days=3)).isoformat()
                else:
                    # If we don't have a user_id, try to look up profile by email
                    try:
                        user_data = supabase.table("users").select("id,tier,trial_ends_at").eq("email", user_email).execute()
                        if user_data and getattr(user_data, "data", None) and len(user_data.data) > 0:
                            user_tier = user_data.data[0].get("tier", "free")
                            trial_ends_at = user_data.data[0].get("trial_ends_at")
                            user_id = user_data.data[0].get("id") or user_id
                        else:
                            trial_ends_at = (datetime.utcnow() + timedelta(days=3)).isoformat()
                            insert_res = supabase.table("users").insert({
                                "email": user_email,
                                "tier": "free",
                                "trial_ends_at": trial_ends_at,
                                "created_at": "now()"
                            }).execute()
                            try:
                                if getattr(insert_res, "data", None) and len(insert_res.data) > 0:
                                    user_id = insert_res.data[0].get("id") or user_id
                            except Exception:
                                pass
                    except Exception as query_by_email_err:
                        print(f"[WARNING] Could not query users by email {user_email}: {str(query_by_email_err)}")
                        user_tier = "free"
                        trial_ends_at = (datetime.utcnow() + timedelta(days=3)).isoformat()
            except Exception as db_error:
                print(f"[WARNING] Could not fetch/create user tier: {str(db_error)}")
                user_tier = "free"
                trial_ends_at = (datetime.utcnow() + timedelta(days=3)).isoformat()

            session["user"] = {"email": user_email, "tier": user_tier, "id": user_id, "trial_ends_at": trial_ends_at}
            return redirect("/dashboard")
        except Exception as e:
            error_msg = f"Login error: {str(e)}"
            print(f"[ERROR] Login route exception: {error_msg}")
            return render_template("login.html", error="An error occurred during login. Please try again.")

    # Handle GET requests
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


# GENERATE CAPTION (Free Tier)
@app.route("/generate-caption", methods=["POST"])
def generate_caption():
    try:
        user_text = request.form.get("user_text", "")

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You create short, catchy Instagram captions."
                },
                {"role": "user", "content": user_text}
            ]
        )

        # FIXED LINE — NO SUBSCRIPTING ERROR
        ai_caption = response.choices[0].message.content

        return jsonify({"caption": ai_caption})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================
# PREMIUM DASHBOARD
# ==========================

@app.route("/dashboard")
def dashboard():
    try:
        if "user" not in session:
            return redirect("/login")

        user = session.get("user") or {}
        user_email = user.get("email") if isinstance(user, dict) else None
        user_tier = user.get("tier", "free") if isinstance(user, dict) else "free"
        trial_ends_at = user.get("trial_ends_at") if isinstance(user, dict) else None
        
        # Calculate days left on trial
        trial_days_left = None
        if trial_ends_at and user_tier == "free":
            try:
                trial_end = datetime.fromisoformat(trial_ends_at)
                days_left = (trial_end - datetime.utcnow()).days
                trial_days_left = max(0, days_left + 1)  # +1 to include current day
            except Exception as e:
                print(f"[WARNING] Could not calculate trial days: {str(e)}")
        
        return render_template("dashboard_unified.html", user_email=user_email, user_tier=user_tier, trial_days_left=trial_days_left)
    except Exception as e:
        error_msg = f"Dashboard error: {str(e)}"
        print(f"[ERROR] Dashboard route exception: {error_msg}")
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

@app.route("/api/premium-caption", methods=["POST"])
def api_premium_caption():
    # Check if user is premium
    if not is_premium():
        return jsonify({"error": "This feature requires a premium subscription. Please subscribe to use it."}), 403
    
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
        caption = response.choices[0].message.content
        return jsonify({"caption": caption})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hashtags", methods=["POST"])
def api_hashtags():
    # Check if user is premium
    if not is_premium():
        return jsonify({"error": "This feature requires a premium subscription. Please subscribe to use it."}), 403
    
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
        hashtags = response.choices[0].message.content.strip()
        return jsonify({"hashtags": hashtags})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reel-script", methods=["POST"])
def api_reel_script():
    # Check if user is premium
    if not is_premium():
        return jsonify({"error": "This feature requires a premium subscription. Please subscribe to use it."}), 403
    
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
        script = response.choices[0].message.content.strip()
        return jsonify({"script": script})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/post-ideas", methods=["POST"])
def api_post_ideas():
    # Check if user is premium
    if not is_premium():
        return jsonify({"error": "This feature requires a premium subscription. Please subscribe to use it."}), 403
    
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
        ideas = response.choices[0].message.content.strip()
        return jsonify({"ideas": ideas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bio-generator", methods=["POST"])
def api_bio_generator():
    # Check if user is premium
    if not is_premium():
        return jsonify({"error": "This feature requires a premium subscription. Please subscribe to use it."}), 403
    
    data = request.get_json() or {}
    niche = data.get("niche", "")
    vibe = data.get("vibe", "Professional & friendly")

    system = (
        "You are an expert at writing compelling, concise social media bios. "
        "Write 3 unique bio variations, each under 150 characters. "
        "Include relevant emojis and make them memorable and action-oriented."
    )

    user_prompt = (
        f"Niche: {niche}\n"
        f"Vibe: {vibe}\n"
        "Create 3 unique bio variations for this creator."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.85,
        )
        bios = response.choices[0].message.content.strip()
        return jsonify({"bios": bios})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/carousel-captions", methods=["POST"])
def api_carousel_captions():
    # Check if user is premium
    if not is_premium():
        return jsonify({"error": "This feature requires a premium subscription. Please subscribe to use it."}), 403
    
    data = request.get_json() or {}
    topic = data.get("topic", "")
    slide_count = data.get("slide_count", "5")

    system = (
        "You are a carousel post expert. "
        f"Write {slide_count} short, punchy captions for carousel slides. "
        "Each caption should be 1-2 sentences max. "
        "Make them educational, entertaining, or inspiring. "
        "Use relevant emojis. Start each with a slide number."
    )

    user_prompt = f"Topic: {topic}\nCreate captions for a {slide_count}-slide carousel."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,
        )
        captions = response.choices[0].message.content.strip()
        return jsonify({"captions": captions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/engagement-hooks", methods=["POST"])
def api_engagement_hooks():
    # Check if user is premium
    if not is_premium():
        return jsonify({"error": "This feature requires a premium subscription. Please subscribe to use it."}), 403
    
    data = request.get_json() or {}
    content_type = data.get("content_type", "")
    topic = data.get("topic", "")

    system = (
        "You are an expert at creating engagement hooks that get comments. "
        "Generate 5 question-based or statement-based opening hooks "
        "that are designed to spark conversation and boost engagement. "
        "Make them relatable, controversial (but not offensive), or curious."
    )

    user_prompt = (
        f"Content Type: {content_type}\n"
        f"Topic: {topic}\n"
        "Create 5 engagement hooks to start a post or reel."
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
        hooks = response.choices[0].message.content.strip()
        return jsonify({"hooks": hooks})
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
                {
                    "role": "system",
                    "content": (
                        "Write longer, creative Instagram captions "
                        "with emojis."
                    )
                },
                {"role": "user", "content": user_text}
            ]
        )

        ai_caption = response.choices[0].message.content
        return jsonify({"caption": ai_caption})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =====================================================
# RUN THE APP
# =====================================================
if __name__ == "__main__":
    # Don't use debug=True in production
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)