"""Shared Pydantic contract for both scraped.json (deterministic extraction
output) and blueprint.json (post-review output) -- same shape for both, see
docs/blueprint-json-pipeline-plan.md.

Every field has a safe empty default so a freshly constructed model always
serializes all of its keys via model_dump(), satisfying the "section key is
always present, empty if not found" rule -- callers should never need to
special-case a missing key, only an empty value.

Image-reference fields (logo, favicon, background_image, image, icon_image,
photo, badge_image) hold only the project-root-relative storage_path string
already produced by crawler/assets.py -- never a full asset object, never
fabricated by the AI review step.
"""

from pydantic import BaseModel, ConfigDict


class ColorPalette(BaseModel):
    primary: str
    secondary: str
    accent: str


class Fonts(BaseModel):
    heading: str
    body: str


class NavLink(BaseModel):
    label: str
    href: str


class SocialLink(BaseModel):
    platform: str
    url: str


class MetaBlock(BaseModel):
    site_name: str
    tagline: str = ""
    logo: str | None = None
    colors: ColorPalette
    fonts: Fonts
    tone: str = ""
    favicon: str | None = None


class HeroSection(BaseModel):
    headline: str = ""
    subheadline: str = ""
    cta_text: str = ""
    cta_href: str = ""
    background_image: str | None = None


class AboutSection(BaseModel):
    heading: str = ""
    body: str = ""
    image: str | None = None


class ServiceItem(BaseModel):
    title: str
    description: str = ""
    icon_image: str | None = None


class FaqItem(BaseModel):
    question: str
    answer: str = ""


class CtaSection(BaseModel):
    heading: str = ""
    body: str = ""
    cta_text: str = ""
    cta_href: str = ""


class FooterSection(BaseModel):
    links: list[NavLink] = []
    social_links: list[SocialLink] = []
    copyright_text: str = ""


class TestimonialItem(BaseModel):
    quote: str
    author: str = ""
    role: str = ""


class GalleryItem(BaseModel):
    image: str
    caption: str = ""


class TeamMember(BaseModel):
    name: str
    role: str = ""
    bio: str = ""
    photo: str | None = None


class PricingPlan(BaseModel):
    plan: str
    price: str = ""
    features: list[str] = []


class StatItem(BaseModel):
    number: str
    label: str = ""


class CredentialItem(BaseModel):
    name: str = ""
    badge_image: str | None = None


class ContactSection(BaseModel):
    address: str = ""
    email: str = ""
    phone: str = ""
    hours: str = ""
    map: str | None = None


class BlogItem(BaseModel):
    title: str
    excerpt: str = ""
    date: str = ""


class AdditionalSection(BaseModel):
    """Real content found on the page that doesn't match any of the 14
    named section types above -- the schema's 16 keys are a template of
    common sections, not an exhaustive/closed contract. Preserves such
    content under its own site-derived heading (key/title) instead of
    dropping it or force-fitting it into the wrong bucket (e.g. into
    `about`)."""

    key: str
    title: str
    body: str = ""
    items: list[str] = []
    images: list[str] = []


class PageSections(BaseModel):
    hero: HeroSection = HeroSection()
    about: AboutSection = AboutSection()
    services_features: list[ServiceItem] = []
    faq: list[FaqItem] = []
    cta_section: CtaSection = CtaSection()
    footer: FooterSection = FooterSection()
    testimonials: list[TestimonialItem] = []
    gallery_portfolio: list[GalleryItem] = []
    team: list[TeamMember] = []
    pricing: list[PricingPlan] = []
    stats_social_proof: list[StatItem] = []
    credentials_awards: list[CredentialItem] = []
    contact: ContactSection = ContactSection()
    blog_news: list[BlogItem] = []
    additional_sections: list[AdditionalSection] = []


# Section keys the AI review step is allowed to rewrite (Mandatory,
# text-bearing). Kept here (not in blueprint_review.py) since it's a
# property of the schema itself -- the one place both the extraction and
# review modules can import it from without a circular import.
MANDATORY_TEXT_SECTIONS = ("hero", "about", "services_features", "faq", "cta_section")

# All Optional/no-fabrication section keys -- the review step must never
# populate these when empty, and never receive them in an LLM request.
OPTIONAL_SECTIONS = (
    "testimonials",
    "gallery_portfolio",
    "team",
    "pricing",
    "stats_social_proof",
    "credentials_awards",
    "contact",
    "blog_news",
)


class PageImage(BaseModel):
    """One image found on the page, regardless of whether it was also
    assigned to a specific section field -- exists so that every downloaded
    image is visible somewhere in the JSON (not just the handful picked out
    for logo/hero/icon/etc. roles), so a reviewing LLM always has the full
    set of real images to choose from."""

    path: str
    alt: str = ""


class PageBlueprint(BaseModel):
    page_url: str
    sections: PageSections = PageSections()
    all_images: list[PageImage] = []


class BlueprintDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meta: MetaBlock
    navigation: list[NavLink] = []
    pages: list[PageBlueprint]
