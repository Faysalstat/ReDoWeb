"""Deterministic (no-AI) rendering of a BlueprintDocument into the old
design.md shape (YAML frontmatter + freeform markdown body), so
app/ai/site_generator.py -- explicitly out of scope for the structured-JSON
blueprint pipeline -- keeps working unchanged until a follow-up plan
rewires it to read blueprint.json directly. See
docs/blueprint-json-pipeline-plan.md.

Only touches fields postprocess.parse_frontmatter() and site_generator.py
actually read: site_name, colors, logo, fonts (tone/tagline are included
too since they're harmless extra frontmatter keys).
"""

import yaml

from .blueprint_schema import BlueprintDocument, PageSections


def render_design_md_compat(blueprint: BlueprintDocument) -> str:
    frontmatter = {
        "site_name": blueprint.meta.site_name,
        "colors": blueprint.meta.colors.model_dump(),
        "logo": blueprint.meta.logo,
        "fonts": blueprint.meta.fonts.model_dump(),
    }
    if blueprint.meta.tone:
        frontmatter["tone"] = blueprint.meta.tone
    if blueprint.meta.tagline:
        frontmatter["tagline"] = blueprint.meta.tagline

    front = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=True).strip()
    body = _render_body(blueprint)
    return f"---\n{front}\n---\n\n{body}"


def _render_body(blueprint: BlueprintDocument) -> str:
    lines: list[str] = []

    if blueprint.navigation:
        lines.append("## Navigation")
        for link in blueprint.navigation:
            lines.append(f"- {link.label} ({link.href})")
        lines.append("")

    for index, page in enumerate(blueprint.pages):
        page_title = "Home Page" if index == 0 else page.page_url
        lines.append(f"## {page_title}")
        lines.extend(_render_sections(page.sections))

    return "\n".join(lines).strip() + "\n"


def _render_sections(sections: PageSections) -> list[str]:
    lines: list[str] = []

    if sections.hero.headline or sections.hero.subheadline:
        lines.append("### Hero")
        if sections.hero.headline:
            lines.append(f"Headline: {sections.hero.headline}")
        if sections.hero.subheadline:
            lines.append(f"Subheading: {sections.hero.subheadline}")
        if sections.hero.cta_text:
            lines.append(f"CTA: {sections.hero.cta_text} ({sections.hero.cta_href})")
        lines.append("")

    if sections.about.heading or sections.about.body:
        lines.append("### About")
        if sections.about.heading:
            lines.append(f"**{sections.about.heading}**")
        if sections.about.body:
            lines.append(sections.about.body)
        lines.append("")

    if sections.services_features:
        lines.append("### Services / Features")
        for item in sections.services_features:
            lines.append(f"- **{item.title}**: {item.description}" if item.description else f"- **{item.title}**")
        lines.append("")

    if sections.faq:
        lines.append("### FAQ")
        for item in sections.faq:
            lines.append(f"- **{item.question}** {item.answer}")
        lines.append("")

    if sections.cta_section.heading or sections.cta_section.body:
        lines.append("### Call To Action")
        if sections.cta_section.heading:
            lines.append(f"**{sections.cta_section.heading}**")
        if sections.cta_section.body:
            lines.append(sections.cta_section.body)
        if sections.cta_section.cta_text:
            lines.append(f"CTA: {sections.cta_section.cta_text} ({sections.cta_section.cta_href})")
        lines.append("")

    if sections.testimonials:
        lines.append("### Testimonials")
        for item in sections.testimonials:
            attribution = f" -- {item.author}" if item.author else ""
            lines.append(f'- "{item.quote}"{attribution}')
        lines.append("")

    if sections.team:
        lines.append("### Team")
        for member in sections.team:
            role = f" ({member.role})" if member.role else ""
            lines.append(f"- **{member.name}**{role}: {member.bio}" if member.bio else f"- **{member.name}**{role}")
        lines.append("")

    if sections.pricing:
        lines.append("### Pricing")
        for plan in sections.pricing:
            features = ", ".join(plan.features)
            lines.append(f"- **{plan.plan}** ({plan.price}): {features}" if plan.price else f"- **{plan.plan}**: {features}")
        lines.append("")

    if sections.stats_social_proof:
        lines.append("### By The Numbers")
        for stat in sections.stats_social_proof:
            lines.append(f"- {stat.number} {stat.label}")
        lines.append("")

    if sections.credentials_awards:
        lines.append("### Credentials / Awards")
        for cred in sections.credentials_awards:
            lines.append(f"- {cred.name}")
        lines.append("")

    if sections.blog_news:
        lines.append("### Blog / News")
        for post in sections.blog_news:
            lines.append(f"- **{post.title}**: {post.excerpt}" if post.excerpt else f"- **{post.title}**")
        lines.append("")

    if sections.contact.email or sections.contact.phone or sections.contact.address:
        lines.append("### Contact")
        if sections.contact.email:
            lines.append(f"- Email: {sections.contact.email}")
        if sections.contact.phone:
            lines.append(f"- Phone: {sections.contact.phone}")
        if sections.contact.address:
            lines.append(f"- Address: {sections.contact.address}")
        if sections.contact.hours:
            lines.append(f"- Hours: {sections.contact.hours}")
        lines.append("")

    return lines
