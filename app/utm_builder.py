import re
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


APPROVED_SOURCES = [
    "google",
    "youtube",
    "reddit",
    "meta",
    "linkedin",
    "x",
    "apollo",
    "newsletter",
]

APPROVED_MEDIA = [
    "cpc",
    "paid_social",
    "paid_video",
    "email",
    "cold_email",
    "organic_social",
    "organic_video",
    "organic_comment",
    "partner",
    "affiliate",
]

OWNER_OPTIONS = [
    ("phil", "Phil"),
    ("clint", "Clint"),
    ("partner", "Partner"),
]

QA_STATUS_OPTIONS = [
    ("draft", "Draft"),
    ("ready", "Ready for QA"),
    ("approved", "Approved"),
]

CHANNEL_OPTIONS = [
    ("google_ads", "Google Ads"),
    ("youtube_paid", "YouTube Ads"),
    ("youtube_owned", "Owned YouTube"),
    ("youtube_partner", "Partner YouTube"),
    ("reddit_paid", "Reddit Ads"),
    ("meta_paid", "Meta Ads"),
    ("cold_email", "Cold Email"),
    ("founder_social", "Founder Social"),
    ("blog_distribution", "Blog Distribution"),
    ("newsletter", "Newsletter"),
]

OBJECTIVE_OPTIONS = [
    ("acq", "Acquisition"),
    ("activation", "Activation"),
    ("retarget", "Retargeting"),
    ("retention", "Retention"),
]

ASSET_TYPE_OPTIONS = [
    ("video", "Video"),
    ("image", "Image"),
    ("email", "Email"),
    ("creator", "Creator"),
    ("link", "Link"),
    ("comment", "Comment"),
]

CONTEXT_PRESETS = {
    "newsletter": {
        "label": "Newsletter Email",
        "utm_source": "newsletter",
        "utm_medium": "email",
        "asset_type": "email",
        "placement": "main-cta",
    },
    "google_ads": {
        "label": "Google Ads",
        "utm_source": "google",
        "utm_medium": "cpc",
        "asset_type": "image",
        "placement": "ad-main",
    },
    "youtube_paid": {
        "label": "Paid YouTube",
        "utm_source": "youtube",
        "utm_medium": "paid_video",
        "asset_type": "video",
        "placement": "ad-main",
    },
    "youtube_owned": {
        "label": "Owned YouTube",
        "utm_source": "youtube",
        "utm_medium": "organic_video",
        "asset_type": "video",
        "placement": "description-main-cta",
    },
    "youtube_partner": {
        "label": "Partner YouTube",
        "utm_source": "youtube",
        "utm_medium": "partner",
        "asset_type": "creator",
        "placement": "creator-description",
    },
    "reddit_paid": {
        "label": "Paid Reddit",
        "utm_source": "reddit",
        "utm_medium": "paid_social",
        "asset_type": "image",
        "placement": "ad-main",
    },
    "meta_paid": {
        "label": "Meta Ads",
        "utm_source": "meta",
        "utm_medium": "paid_social",
        "asset_type": "image",
        "placement": "ad-main",
    },
    "cold_email": {
        "label": "Cold Email",
        "utm_source": "apollo",
        "utm_medium": "cold_email",
        "asset_type": "email",
        "placement": "cta-primary",
    },
    "founder_social": {
        "label": "Founder Social",
        "utm_source": "linkedin",
        "utm_medium": "organic_social",
        "asset_type": "link",
        "placement": "post-link",
    },
    "blog_distribution": {
        "label": "Blog Distribution",
        "utm_source": "linkedin",
        "utm_medium": "organic_social",
        "asset_type": "link",
        "placement": "post-link",
    },
}

UTM_ID_REQUIRED_MEDIA = {
    "cpc",
    "paid_social",
    "paid_video",
    "cold_email",
    "partner",
    "affiliate",
}


def slugify_utm_value(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("_", "-")
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def get_period_slug(today: date | None = None) -> str:
    today = today or date.today()
    quarter = ((today.month - 1) // 3) + 1
    return f"q{quarter}-{today.year}"


def medium_requires_utm_id(medium: str) -> bool:
    return slugify_utm_value(medium).replace("-", "_") in UTM_ID_REQUIRED_MEDIA


def build_campaign_name(
    objective: str,
    offer: str,
    period: str,
    audience: str = "",
    theme: str = "",
) -> str:
    parts = [
        slugify_utm_value(objective),
        slugify_utm_value(offer),
        slugify_utm_value(audience),
        slugify_utm_value(theme),
        slugify_utm_value(period),
    ]
    return "-".join(part for part in parts if part)


def build_campaign_display_name(
    objective: str,
    offer: str,
    audience: str = "",
    theme: str = "",
    period: str = "",
) -> str:
    labels = [
        objective.replace("-", " ").title() if objective else "",
        offer.replace("-", " ").title() if offer else "",
        audience.replace("-", " ").title() if audience else "",
        theme.replace("-", " ").title() if theme else "",
        period.upper() if period else "",
    ]
    return " | ".join(label for label in labels if label)


def build_content_name(asset_type: str, placement: str, variant: str) -> str:
    parts = [slugify_utm_value(part) for part in [asset_type, placement, variant]]
    return "-".join(part for part in parts if part)


def suggest_utm_id(source: str, medium: str, period: str, today: date | None = None) -> str:
    today = today or date.today()
    date_stamp = today.strftime("%m%d")
    parts = [
        slugify_utm_value(source),
        slugify_utm_value(medium).replace("-", "_"),
        slugify_utm_value(period),
        date_stamp,
    ]
    return "-".join(part for part in parts if part)


def build_final_url(
    base_url: str,
    source: str,
    medium: str,
    campaign: str,
    content: str,
    term: str = "",
    utm_id: str = "",
) -> str:
    parsed = urlsplit(base_url.strip())
    existing_params = parse_qsl(parsed.query, keep_blank_values=True)
    params = {key: value for key, value in existing_params}
    params["utm_source"] = source
    params["utm_medium"] = medium
    params["utm_campaign"] = campaign
    params["utm_content"] = content
    if term:
        params["utm_term"] = term
    else:
        params.pop("utm_term", None)
    if utm_id:
        params["utm_id"] = utm_id
    else:
        params.pop("utm_id", None)
    query = urlencode(params)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def validate_base_url(base_url: str) -> bool:
    parsed = urlsplit((base_url or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_campaign_core_payload(raw: dict, today: date | None = None) -> tuple[dict, list[str]]:
    today = today or date.today()
    errors: list[str] = []

    objective = slugify_utm_value(raw.get("objective", ""))
    offer = slugify_utm_value(raw.get("offer", ""))
    audience = slugify_utm_value(raw.get("audience", ""))
    theme = slugify_utm_value(raw.get("theme", ""))
    period = get_period_slug(today)

    if objective not in {value for value, _ in OBJECTIVE_OPTIONS}:
        errors.append("Choose a valid campaign objective.")
    if not offer:
        errors.append("Add the main offer or focus for this campaign core.")

    campaign_slug = build_campaign_name(
        objective=objective,
        offer=offer,
        audience=audience,
        theme=theme,
        period=period,
    )
    display_name = build_campaign_display_name(
        objective=objective,
        offer=offer,
        audience=audience,
        theme=theme,
        period=period,
    )

    return {
        "objective": objective,
        "offer": offer,
        "audience": audience,
        "theme": theme,
        "period": period,
        "campaign_slug": campaign_slug,
        "display_name": display_name,
    }, errors


def normalize_builder_payload(
    raw: dict,
    campaign_slug: str,
    period: str,
    today: date | None = None,
) -> tuple[dict, list[str]]:
    today = today or date.today()
    errors: list[str] = []

    base_url = (raw.get("base_url") or "").strip()
    source = slugify_utm_value(raw.get("utm_source", ""))
    medium = slugify_utm_value(raw.get("utm_medium", "")).replace("-", "_")
    asset_type = slugify_utm_value(raw.get("asset_type", ""))
    placement = slugify_utm_value(raw.get("placement", ""))
    variant = slugify_utm_value(raw.get("variant", "")) or "v1"
    utm_term = slugify_utm_value(raw.get("utm_term", ""))
    utm_id = slugify_utm_value(raw.get("utm_id", ""))
    channel = slugify_utm_value(raw.get("channel", ""))
    owner = slugify_utm_value(raw.get("owner", "")) or "phil"
    qa_status = slugify_utm_value(raw.get("qa_status", "")) or "draft"
    qa_approved_by = (raw.get("qa_approved_by") or "").strip()
    notes = (raw.get("notes") or "").strip()

    if not campaign_slug:
        errors.append("Choose or create a campaign core first.")
    if not validate_base_url(base_url):
        errors.append("Enter a full landing page URL starting with http:// or https://.")
    if source not in APPROVED_SOURCES:
        errors.append("Select an approved utm_source.")
    if medium not in APPROVED_MEDIA:
        errors.append("Select an approved utm_medium.")
    if not asset_type:
        errors.append("Select an asset type for utm_content.")
    if not placement:
        errors.append("Add a placement value for utm_content.")
    if owner not in {value for value, _ in OWNER_OPTIONS}:
        errors.append("Select a valid owner.")
    if qa_status not in {value for value, _ in QA_STATUS_OPTIONS}:
        errors.append("Select a valid QA status.")
    if medium_requires_utm_id(medium) and not utm_id:
        errors.append("utm_id is required for paid, partner, affiliate, and outbound link types.")

    utm_content = build_content_name(asset_type, placement, variant)
    final_url = ""

    if not errors:
        final_url = build_final_url(
            base_url=base_url,
            source=source,
            medium=medium,
            campaign=campaign_slug,
            content=utm_content,
            term=utm_term,
            utm_id=utm_id,
        )

    return {
        "base_url": base_url,
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": campaign_slug,
        "utm_content": utm_content,
        "utm_term": utm_term,
        "utm_id": utm_id,
        "channel": channel,
        "placement": placement,
        "owner": owner,
        "qa_status": qa_status,
        "qa_approved_by": qa_approved_by,
        "notes": notes,
        "asset_type": asset_type,
        "variant": variant,
        "requires_utm_id": medium_requires_utm_id(medium),
        "suggested_utm_id": suggest_utm_id(source, medium, period, today=today),
        "final_url": final_url,
        "today_stamp": today.strftime("%Y%m%d"),
        "period": period,
    }, errors
