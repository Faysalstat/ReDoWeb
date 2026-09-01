# Recipe catalog

Each recipe is a candidate design-system anchor for the AI design-system-generation step (`app/ai/design_system_generation.py`). The real brand colors/fonts/site data always override a recipe's illustrative palette/type choices — a recipe supplies *relationships and signature moves* (how much whitespace, how bold the type, how rounded, how loud the color), not literal hex values to copy.

| Recipe | School | Best for | Keywords used by the deterministic pre-filter |
|---|---|---|---|
| `linear` | Modern Tool / Builder SaaS | software/SaaS, professional/technical services | corporate, professional, trust, trusted, trustworthy, enterprise, business, saas, polished, serious |
| `vercel-mesh` | Modern Tool / Builder SaaS | technical/platform products, tools | modern, sleek, dark, tech, technical, minimal, minimalist |
| `aesop` | Editorial / Minimalist | premium retail/boutique, wellness/beauty, hospitality | warm, premium, refined, quiet, artisan, boutique |
| `muji-kenya-hara` | Editorial / Minimalist | houseware/object retail, slow-living, craft goods | calm, calming, natural, minimal, handcrafted, quiet |
| `apple-hig` | Editorial / Minimalist | premium consumer product/service | premium, polished, confident, sophisticated, clean |
| `pentagram` | Information Architecture | agencies/studios, professional/creative services | bold, confident, graphic, direct, strong |
| `mailchimp-freddie` | Warm Humanist | local/small businesses, creator/community products | friendly, warm, approachable, fun, personal, playful |
| `headspace-meditation` | Warm Humanist | wellness/health/coaching | calm, caring, gentle, cozy, welcoming, soothing |
| `industrial-craft` | Custom | trades, manufacturing, auto/equipment repair, contractors | industrial, technical, mechanical, rugged, precise, functional, engineering |
| `vibrant-friendly` | Custom | local retail, food/hospitality, family-facing services | vibrant, colorful, playful, fun, dynamic, expressive |

Default candidate set (used when `tone` is empty/unmatched): `linear`, `aesop`, `mailchimp-freddie` — a broad spread across professional, refined, and friendly registers.
