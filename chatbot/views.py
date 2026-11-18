import json
import re
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.cache import cache

from bookings.views import get_client_ip
from .engine import answer, _get_default_quick_replies

# Rate limiting constants
CHAT_RATE_LIMIT_MESSAGES = 20
CHAT_RATE_LIMIT_WINDOW_SECONDS = 600  # 10 minutes
UNANSWERED_RATE_LIMIT_PER_HOUR = 10
UNANSWERED_RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour


@require_http_methods(["POST"])
def chat_ask(request):
    """
    POST /chat/ask/
    Expects JSON: {"message": "..."}
    Returns JSON: {"answer": "...", "actions": [...], "matched": bool}
    """
    # 1. Parse JSON body
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    raw_message = data.get("message", "")
    if not isinstance(raw_message, str):
        return JsonResponse({"error": "Message must be a string."}, status=400)

    # 2. Strip control characters
    cleaned_message = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', raw_message).strip()

    # 3. Validation: reject empty
    if not cleaned_message:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)

    # 4. Validation: max 300 characters
    if len(cleaned_message) > 300:
        return JsonResponse({"error": "Message exceeds the 300-character limit."}, status=400)

    # 5. Per-client Rate Limiting (20 messages per 10 minutes)
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

    # 6. Check client hourly unanswered question cap before calling engine
    unanswered_cache_key = f"chat_unanswered_ip_{client_ip}"
    unanswered_count = cache.get(unanswered_cache_key, 0)
    client_capped_unanswered = (unanswered_count >= UNANSWERED_RATE_LIMIT_PER_HOUR)

    # Pass to engine
    response_data = answer(cleaned_message)

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
    Returns list of quick-reply topics for the chatbot launcher / greeting.
    """
    topics = [
        {"label": "Rooms & Rates", "topic": "rooms"},
        {"label": "Restaurant & Menu", "topic": "restaurant"},
        {"label": "Facilities", "topic": "facilities"},
        {"label": "How to Reach", "topic": "how to reach"},
        {"label": "Check-in & Policies", "topic": "hotel policies"},
        {"label": "Contact & Phone", "topic": "contact number"},
    ]
    return JsonResponse({"topics": topics})

