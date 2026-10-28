import {
  Award,
  CheckCircle,
  Clock,
  Download,
  FileSearch,
  Globe,
  Layers,
  Lock,
  LucideIconData,
  Palette,
  Search,
  ShieldCheck,
  Sparkles,
  Wand2,
  Zap,
} from 'lucide-angular';

import { Accent } from '../../shared/design/accents';
import { Faq } from '../../shared/components/faq-accordion.component';

// ════════════════════════════════════════════════════════════════════════
// PLACEHOLDER — replace before launch.
// Everything in this block is the blueprint's illustrative social proof,
// not real ReDoWebs data: counters, ratings, customer counts, testimonials,
// the "as featured in" marquee and the "trusted by" logo strip (third-party
// trademarks — check you're entitled to show them). Kept on purpose so the
// page looks complete while real numbers and quotes are gathered.
// ════════════════════════════════════════════════════════════════════════

export const LIVE_COUNTER = {
  today: 23,
  total: 4847,
  rating: '4.9/5',
  customers: '2,300+',
};

export const STATS: { value: number; suffix: string; label: string; color: string }[] = [
  { value: 12847, suffix: '+', label: 'Websites Redesigned', color: 'text-green-400' },
  { value: 98, suffix: '%', label: 'Customer Satisfaction', color: 'text-blue-400' },
  { value: 15, suffix: ' min', label: 'Average Turnaround', color: 'text-orange-400' },
  { value: 3, suffix: 'x', label: 'Avg. Conversion Lift', color: 'text-pink-400' },
];

export const BRANDS: { name: string; style: string }[] = [
  { name: 'Forbes', style: 'font-serif font-black tracking-tight text-white/70' },
  { name: 'TechCrunch', style: 'font-sans font-black text-green-400/70' },
  { name: 'Entrepreneur', style: 'font-serif font-bold italic text-white/70' },
  { name: 'Wired', style: 'font-sans font-black tracking-widest uppercase text-white/70' },
  { name: 'Product Hunt', style: 'font-sans font-bold text-orange-400/70' },
  { name: 'Shopify', style: 'font-sans font-bold text-green-500/70' },
  { name: 'G2', style: 'font-sans font-black text-orange-500/70' },
  { name: 'Capterra', style: 'font-sans font-bold text-blue-400/70' },
  { name: 'Inc. 500', style: 'font-serif font-black text-white/70' },
  { name: 'HubSpot', style: 'font-sans font-bold text-orange-400/70' },
];

export const TESTIMONIALS: { name: string; role: string; quote: string; avatar: string }[] = [
  { name: 'Sarah M.', role: 'E-commerce Owner', quote: 'Got professional designs in minutes. Went with the Pro one and saw a 40% conversion increase.', avatar: '/assets/images/testimonials/sarah-m.jpg' },
  { name: 'James L.', role: 'Agency Owner', quote: 'Perfect for pitching redesigns to clients. The quality is professional-grade at an unbeatable price.', avatar: '/assets/images/testimonials/james-l.jpg' },
  { name: 'Maria C.', role: 'Small Business', quote: 'No design budget, but ReDoWebs made it affordable. Looks like it cost thousands.', avatar: '/assets/images/testimonials/maria-c.jpg' },
  { name: 'David K.', role: 'SaaS Founder', quote: 'The redesigns landed us 5 new enterprise clients. Incredible ROI.', avatar: '/assets/images/testimonials/david-k.jpg' },
  { name: 'Amanda R.', role: 'Freelancer', quote: 'Now I offer redesigns to clients as a premium service. ReDoWebs is my secret weapon.', avatar: '/assets/images/testimonials/amanda-r.jpg' },
  { name: 'Michael T.', role: 'Marketing Director', quote: 'The conversion optimization is spot-on. Best investment we made this year.', avatar: '/assets/images/testimonials/michael-t.jpg' },
  { name: 'Rachel P.', role: 'Restaurant Owner', quote: 'Our online reservations tripled after switching to the redesign. Absolutely worth every penny.', avatar: '/assets/images/testimonials/rachel-p.jpg' },
  { name: 'Tom W.', role: 'Real Estate Agent', quote: 'I was skeptical at first but the result blew me away. My leads doubled in the first month.', avatar: '/assets/images/testimonials/tom-w.jpg' },
  { name: 'Priya S.', role: 'Health & Wellness Coach', quote: 'Professional, fast, and the designs actually convert. My coaching bookings went through the roof.', avatar: '/assets/images/testimonials/priya-s.jpg' },
];

export const TRUSTED_LOGOS: { alt: string; src: string }[] = [
  { alt: 'Google', src: '/assets/logos/trusted/google.png' },
  { alt: 'Amazon', src: '/assets/logos/trusted/amazon.svg' },
  { alt: 'Microsoft', src: '/assets/logos/trusted/microsoft.svg' },
  { alt: 'Figma', src: '/assets/logos/trusted/figma.svg' },
  { alt: 'Adobe', src: '/assets/logos/trusted/adobe.ico' },
  { alt: 'Slack', src: '/assets/logos/trusted/slack.ico' },
];

/** Agency / DIY columns are the blueprint's illustrative figures. */
export const COMPARISON: { feature: string; us: string | boolean | null; agency: string | boolean | null; diy: string | boolean | null }[] = [
  { feature: 'Time to get designs', us: 'Under 30 min', agency: '4–8 weeks', diy: '2–4 weeks' },
  { feature: 'Cost', us: 'Pay per download', agency: '$3,000–$15,000', diy: '$200–$500/yr' },
  { feature: 'Live interactive preview', us: true, agency: false, diy: false },
  { feature: 'Your real content kept', us: true, agency: true, diy: false },
  { feature: 'Download-ready files', us: true, agency: true, diy: false },
  { feature: 'No designer needed', us: true, agency: false, diy: true },
  { feature: 'SEO pass included', us: true, agency: null, diy: false },
  { feature: 'Free re-downloads', us: true, agency: false, diy: null },
];

// ════════════════════════════════════════════════════════════════════════
// Real product copy: how ReDoWebs actually works.
// ════════════════════════════════════════════════════════════════════════

export const STEPS = [
  { step: '01', title: 'Paste your URL', desc: 'We crawl what is publicly on your site: copy, images, structure and contact details. Sites up to 20 pages.' },
  { step: '02', title: 'We read your brand', desc: 'Your logo, colors, fonts and tone are pulled into a structured blueprint. Nothing about your business is invented.' },
  { step: '03', title: 'AI redesigns it', desc: 'Each design tier rebuilds your home page in its own style. Preview every one live in your browser, free.' },
  { step: '04', title: 'Buy, build, launch', desc: 'Buy the design you like, generate every page of your site, run the SEO agent, and download the files.' },
];

export const FEATURES: { title: string; desc: string; icon: LucideIconData; accent: Accent }[] = [
  { title: 'Live previews', desc: 'Click through every redesign on desktop and phone before you spend a credit on it.', icon: Globe, accent: 'cyan' },
  { title: 'Multiple design tiers', desc: 'Each tier is a different design direction for the same site, so you get a real choice.', icon: Palette, accent: 'purple' },
  { title: 'All your pages', desc: 'After buying, generate every page of your site in the same style as the home page you picked.', icon: Layers, accent: 'blue' },
  { title: 'Download as a ZIP', desc: 'Plain HTML and CSS you can host anywhere. Re-download a design you bought at no cost.', icon: Download, accent: 'orange' },
  { title: 'SEO agent', desc: 'On Pro and Premium: titles, meta descriptions, headings, alt text, structured data, sitemap and robots.txt.', icon: Search, accent: 'green' },
  { title: 'No made-up facts', desc: 'Testimonials, prices, team members and contact details are never invented. If your site lacks them, so does the redesign.', icon: ShieldCheck, accent: 'pink' },
];

export const REASONS: { title: string; desc: string; icon: LucideIconData; accent: Accent }[] = [
  { title: 'Minutes, not months', desc: 'Agencies take weeks to show a first concept. You see finished redesigns of your own site the same day.', icon: Clock, accent: 'cyan' },
  { title: 'Pay only for what you keep', desc: 'Previews are free. Credits are only spent when you buy the design you want to download.', icon: Zap, accent: 'green' },
  { title: 'Built from your site', desc: 'Your copy, images and brand colors carry over, so the redesign still sounds like your business.', icon: Wand2, accent: 'purple' },
  { title: 'Ready to launch', desc: 'Standard HTML and CSS files, with sitemap and search tags, that any host can serve.', icon: Award, accent: 'orange' },
];

export const DEMO_STEPS: { label: string; icon: LucideIconData; color: string }[] = [
  { label: 'Paste your URL', icon: Globe, color: 'text-cyan-400' },
  { label: 'AI generates your designs', icon: Sparkles, color: 'text-purple-400' },
  { label: 'Download & launch', icon: Download, color: 'text-green-400' },
];

export const TRUST_BADGES: { title: string; desc: string; icon: LucideIconData; color: string }[] = [
  { title: 'No fabricated content', desc: 'Facts about your business come only from your site.', icon: CheckCircle, color: 'text-green-400' },
  { title: 'Private previews', desc: 'Previews are only visible to you. Nothing is published.', icon: Lock, color: 'text-blue-400' },
  { title: 'Free to preview', desc: 'See every design before spending a credit.', icon: FileSearch, color: 'text-yellow-400' },
  { title: 'Secure checkout', desc: 'Pay by PayPal or card. We never see your card details.', icon: ShieldCheck, color: 'text-pink-400' },
];

export const FAQS: Faq[] = [
  { q: 'What does it cost?', a: 'Submitting a site and previewing the redesigns is free. Downloading a design costs credits, which you buy in one-time packs. There is no subscription. Re-downloading a design you already bought is free.' },
  { q: 'Which websites can I submit?', a: 'Small static sites up to 20 pages that you own or are authorized to redesign. Sites that require a login, block crawling, or have more than 20 pages are turned down.' },
  { q: 'Will the redesign make things up about my business?', a: 'No. Marketing copy can be polished, but testimonials, prices, team members, awards, statistics and contact details are only ever taken from your site. If your site has none, the redesign has none.' },
  { q: 'What do I get when I buy a design?', a: 'A ZIP of plain HTML and CSS. On multi-page sites you can then generate every page in the same style, and on Pro and Premium you can run the SEO agent. Each runs once per purchase, with a retry if it fails.' },
  { q: 'Is my live site changed?', a: 'Never. We only read your public pages to build a replacement. You decide if and where to publish the files.' },
  { q: 'How long does it take?', a: 'Usually 15 to 30 minutes from submitting the URL to seeing the previews. You can close the tab and come back to the project later.' },
];
