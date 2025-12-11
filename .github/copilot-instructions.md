# AI Assistant Pros - Copilot Instructions

## Project Overview
**AI Assistant Pros** is a Flask-based SaaS application providing AI-powered social media content generation tools. It combines a freemium model (caption generator) with premium subscription features (advanced captions, hashtags, reel scripts, post ideas) using Stripe for billing.

### Architecture
- **Backend**: Flask (Python) handling auth, API routes, and Stripe integration
- **Frontend**: Jinja2 templates + vanilla JavaScript (no framework)
- **Auth**: Supabase (email/password via `supabase.auth`)
- **Database**: Supabase (referenced but not directly queried in current routes)
- **AI Engine**: OpenAI API (gpt-3.5-turbo and gpt-4o-mini)
- **Payments**: Stripe (subscription checkout)
- **Deployment**: Render (via gunicorn)

## Critical Developer Workflows

### Running Locally
```bash
python app.py  # Flask dev server on http://127.0.0.1:5000
```
Requires `.env` with all keys from `.env.example`.

### Adding New AI Endpoints
1. Create route in `app.py` (pattern: `/api/{feature-name}`, method=POST)
2. Accept `data = request.get_json()` for parameters
3. Use `client.chat.completions.create()` with system/user roles
4. Return JSON: `jsonify({"key": response_content})`
5. Example temperature tuning: `temperature=0.9` for creative tasks

### Environment Variables
- **Auth**: `SECRET_KEY` / `APP_SECRET`, `SUPABASE_URL`, `SUPABASE_KEY`
- **Stripe**: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `DOMAIN_URL`
- **AI**: `OPENAI_API_KEY`
- **Fallback keys**: Project accepts both `SUPABASE_KEY` and `SUPABASE_SERVICE_ROLE`

## Project Patterns & Conventions

### Session Management
User authentication via Flask sessions. Pattern:
```python
session["user"] = {"email": user_email}  # Login
session.pop("user", None)                # Logout
if "user" not in session: return redirect("/login")  # Guard
```
Dashboard and premium endpoints check session to gate access.

### Response Handling
- **AI Responses**: Use `response.choices[0].message.content`
- **Supabase**: Methods return either dict or object with `.error` / `.data` attributes — **normalize both** (see `login()` for pattern)
- **Error Returns**: Always `jsonify({"error": str(e)}), 500`

### Naming Conventions
- Routes: kebab-case (`/create-checkout-session`, `/premium-caption`)
- DOM elements: snake_case (`user_text`, `result`)
- Data keys: snake_case in JSON payloads

### Template Structure
- Minimal CSS (mostly inline `<style>` blocks)
- Vanilla JS functions (e.g., `sendCaption()`) triggered by button `onclick`
- No bundler or build step
- Form submissions use `fetch()` with JSON

## Key Files & Their Roles

| File | Purpose |
|------|---------|
| `app.py` | All routes, auth, Stripe, AI calls; 387 lines |
| `templates/dashboard.html` | Main premium UI hub; 573 lines with sidebar nav |
| `templates/caption.html` | Free tier demo; minimal single-input form |
| `templates/landing.html` | Public home page |
| `templates/login.html`, `signup.html` | Auth forms |
| `requirements.txt` | Flask, OpenAI, Stripe, Supabase, gunicorn, etc. |
| `.env.example` | Full config template |

## Integration Points & Quirks

### Stripe Subscription Flow
1. POST `/create-checkout-session` → `stripe.checkout.Session.create(mode="subscription")`
2. Redirect to Stripe-hosted checkout URL
3. Success: `/success` (route exists but does not validate session)
4. Cancel: `/cancel` (no session validation)

### OpenAI Model Choices
- **Free tier**: `gpt-3.5-turbo` (fast, cost-efficient)
- **Premium**: `gpt-4o-mini` (better quality) in `/generate-premium-caption`
- All endpoints use `temperature=0.9` for creative tasks (except hashtags: default 0.7)

### Supabase Auth Details
- Sign-up includes redirect option: `email_redirect_to` → `/login`
- Error handling: Check `response["error"]` exists before accessing message
- Session stores `{"email": user_email}`, not full user object

## Common Tasks

**Add a new free AI feature:**
1. Create route `/api/{feature}` accepting POST with JSON
2. Build system prompt describing the task
3. Call `client.chat.completions.create()` with user description
4. Return `jsonify({"result": content})`
5. Link from `caption.html` or create new template

**Debug session issues:**
Check if user dict is dict vs object: `isinstance(user, dict)` before accessing `.get()`.

**Deploy to Render:**
Procfile runs: `gunicorn app:app`. Ensure all env vars set in Render dashboard.

## Testing Notes
- No test suite present; manual testing via Flask dev server
- Free tier routes (`/caption`, `/generate-caption`) can be tested without login
- Premium routes require `session["user"]` set (login first in UI)
