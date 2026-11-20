import json
import re
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.cache import cache

from bookings.views import get_client_ip
from .engine import answer, answer_intent

# Rate limiting constants
CHAT_RATE_LIMIT_MESSAGES = 20
CHAT_RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes
UNANSWERED_RATE_LIMIT_PER_HOUR = 10
UNANSWERED_RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour


@require_http_methods(["POST"])
def chat_ask(request):
    """
    POST /chat/ask/
    Expects JSON object: {"message": "..."} or {"intent_id": "..."}
    Returns JSON: {"answer": "...", "actions": [...], "matched": bool}
    """
    # 1. Parse JSON body and ensure it is an object
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    # 2. Check for explicit intent ID / button action (separate from free-text matching)
    intent_id = data.get("intent_id") or data.get("topic")
    if intent_id is not None:
        if not isinstance(intent_id, str) or not intent_id.strip():
            return JsonResponse({"error": "Intent ID must be a non-empty string."}, status=400)
        response_data = answer_intent(intent_id.strip())
        return JsonResponse(response_data)

    # 3. Handle free-text message
    if "message" not in data:
        return JsonResponse({"error": "Message field is required."}, status=400)

    raw_message = data.get("message", "")
    if not isinstance(raw_message, str):
        return JsonResponse({"error": "Message must be a string."}, status=400)

    cleaned_message = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', raw_message).strip()

    if not cleaned_message:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)

    if len(cleaned_message) > 300:
        return JsonResponse({"error": "Message exceeds the 300-character limit."}, status=400)

    # 4. Per-client Rate Limiting (20 messages per 10 minutes)
    client_ip = get_client_ip(request) or "unknown"
    ip_cache_key = f"chat_ratelimit_ip_{client_ip}"
    current_count = cache.get(ip_cache_key)

    if current_count is not None and current_count >= CHAT_RATE_LIMIT_MESSAGES:
        return JsonResponse({
            "error": "You have sent quite a few messages. Please wait a few minutes before asking again, or contact our front desk directly."
        }, status=429)

    # Increment rate-limit counter
    if current_count is None:
        cache.set(ip_cache_key, 1, timeout=CHAT_RATE_LIMIT_WINDOW_SECONDS)
    else:
        try:
            cache.incr(ip_cache_key)
        except ValueError:
            cache.set(ip_cache_key, 1, timeout=CHAT_RATE_LIMIT_WINDOW_SECONDS)

    # 5. Check client hourly unanswered question cap before calling engine
    unanswered_cache_key = f"chat_unanswered_ip_{client_ip}"
    unanswered_count = cache.get(unanswered_cache_key, 0)
    client_capped_unanswered = (unanswered_count >= UNANSWERED_RATE_LIMIT_PER_HOUR)

    # Pass to engine (honoring client hourly cap for unanswered question recording)
    response_data = answer(cleaned_message, record_unanswered=not client_capped_unanswered)

    # If the engine couldn't match and would record unanswered, track it against IP cap
    if not response_data.get("matched", False):
        if unanswered_count == 0:
            cache.set(unanswered_cache_key, 1, timeout=UNANSWERED_RATE_LIMIT_WINDOW_SECONDS)
        else:
            try:
                cache.incr(unanswered_cache_key)
            except ValueError:
                cache.set(unanswered_cache_key, 1, timeout=UNANSWERED_RATE_LIMIT_WINDOW_SECONDS)

    return JsonResponse(response_data)


@require_http_methods(["GET"])
def chat_topics(request):
    """
    GET /chat/topics/
    Returns list of quick-reply topics with stable intent IDs.
    """
    topics = [
        {"label": "Rooms & Rates", "intent_id": "rooms_rates", "topic": "rooms_rates"},
        {"label": "Restaurant & Menu", "intent_id": "restaurant", "topic": "restaurant"},
        {"label": "Facilities", "intent_id": "facilities", "topic": "facilities"},
        {"label": "How to Reach", "intent_id": "how_to_reach", "topic": "how_to_reach"},
        {"label": "Check-in & Policies", "intent_id": "hotel_info", "topic": "hotel_info"},
        {"label": "Contact & Phone", "intent_id": "contact", "topic": "contact"},
    ]
    return JsonResponse({"topics": topics})
