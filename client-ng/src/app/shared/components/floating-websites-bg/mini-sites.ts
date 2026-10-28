// The 13 tiny "website screenshot" cards that drift behind the public pages
// (blueprint §7.18), ported from ui-assets/reference/FloatingWebsitesBg.jsx.
// Static, app-authored HTML only -- rendered with bypassSecurityTrustHtml
// because Angular's sanitizer would strip every inline style otherwise.
// Never put user or API data in here.

const nav = (items: string[], color: string, size = 5.5) =>
  items.map((n) => `<span style="color:${color};font-size:${size}px">${n}</span>`).join('');

export const MINI_SITES: string[] = [
  // 1. Digital agency: dark with red accents
  `<div style="width:100%;height:100%;background:#1a1a2e;font-family:system-ui;overflow:hidden">
    <div style="background:#16213e;padding:4px 8px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #0f3460">
      <span style="color:#e94560;font-weight:900;font-size:7px">AGENCY</span>
      <div style="display:flex;gap:5px">${nav(['Home', 'Work', 'About'], '#a8a8b3')}</div>
    </div>
    <div style="padding:10px 8px 6px">
      <div style="font-size:5.5px;color:#e94560;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Creative Studio</div>
      <div style="font-size:13px;font-weight:900;color:#fff;line-height:1.15;margin-bottom:5px;letter-spacing:-0.02em">WEBSITES<br>THAT WIN</div>
      <div style="display:flex;gap:4px">
        <div style="background:#e94560;color:#fff;font-size:5.5px;font-weight:700;padding:3px 7px;border-radius:3px">Our Work</div>
        <div style="border:1px solid #e94560;color:#e94560;font-size:5.5px;padding:3px 6px;border-radius:3px">Contact</div>
      </div>
    </div>
    <div style="display:flex;gap:4px;padding:0 8px">
      ${['UI/UX', 'Branding', 'Dev']
        .map(
          (t) =>
            `<div style="flex:1;background:#0f3460;border-radius:4px;padding:4px 3px;text-align:center"><div style="font-size:5px;color:#e94560;font-weight:700">${t}</div></div>`,
        )
        .join('')}
    </div>
  </div>`,

  // 2. Wedding planner: soft pink
  `<div style="width:100%;height:100%;background:#fff8f5;font-family:Georgia,serif;overflow:hidden">
    <div style="background:#fff;border-bottom:1px solid #fce4d6;padding:4px 8px;display:flex;justify-content:space-between;align-items:center">
      <span style="color:#c9746b;font-weight:700;font-size:7px">💒 WeddingDir</span>
      <div style="background:#f4845f;color:#fff;font-size:5px;padding:2px 6px;border-radius:3px;font-weight:700">Get Started</div>
    </div>
    <div style="background:linear-gradient(rgba(0,0,0,0.35),rgba(0,0,0,0.35)),linear-gradient(135deg,#f9c5a4,#e8a598);height:45px;display:flex;flex-direction:column;justify-content:center;padding:0 8px">
      <div style="color:#fff;font-weight:700;font-size:10px;font-style:italic;line-height:1.2">Find the Perfect<br>Wedding Vendor</div>
      <div style="color:rgba(255,255,255,0.8);font-size:5.5px;margin-top:2px">Search 360,000+ vendors with reviews</div>
    </div>
    <div style="padding:5px 8px;display:flex;gap:3px">
      <div style="flex:1;background:#fff;border:1px solid #fce4d6;border-radius:4px;padding:3px 4px;font-size:5px;color:#aaa">Category...</div>
      <div style="flex:1;background:#fff;border:1px solid #fce4d6;border-radius:4px;padding:3px 4px;font-size:5px;color:#aaa">Location...</div>
      <div style="background:#f4845f;color:#fff;font-size:5.5px;font-weight:700;padding:3px 7px;border-radius:4px">Search</div>
    </div>
    <div style="display:flex;justify-content:space-around;padding:3px 6px">
      ${['💍', '👗', '📷', '🌸', '🎂'].map((e) => `<div style="font-size:10px">${e}</div>`).join('')}
    </div>
  </div>`,

  // 3. Tech / hosting: orange and dark
  `<div style="width:100%;height:100%;background:#fff;font-family:system-ui;overflow:hidden">
    <div style="background:#222;padding:3px 8px;display:flex;justify-content:space-between">
      <span style="color:#aaa;font-size:5px">WELCOME TO TERAHOSTER</span>
      <div style="display:flex;gap:6px">${nav(['Register', 'Login'], '#aaa', 5)}</div>
    </div>
    <div style="padding:5px 8px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee">
      <div style="display:flex;align-items:center;gap:3px">
        <div style="width:8px;height:8px;background:#e05c35;border-radius:2px"></div>
        <span style="font-weight:900;font-size:8px;color:#222">TERA<span style="color:#e05c35">HOSTER</span></span>
      </div>
      <div style="display:flex;gap:6px">${nav(['Home', 'Hosting', 'Web Design'], '#555')}</div>
    </div>
    <div style="display:flex;padding:8px;gap:8px;align-items:center">
      <div style="flex:1">
        <div style="font-size:13px;font-weight:900;color:#222;line-height:1.1">FULLY<br><span style="color:#e05c35">MANAGED</span></div>
        <div style="font-size:6px;color:#666;margin:4px 0">Virtual Servers with unlimited bandwidth</div>
        <div style="display:flex;gap:4px">
          <div style="background:#e05c35;color:#fff;font-size:5.5px;font-weight:700;padding:3px 7px;border-radius:3px">Get Started</div>
          <div style="border:1px solid #ccc;color:#333;font-size:5.5px;padding:3px 6px;border-radius:3px">Contact Us</div>
        </div>
      </div>
      <div style="width:30px;height:38px;background:#f5f5f5;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:16px">👨‍💻</div>
    </div>
    <div style="background:#e05c35;padding:4px 8px;display:flex;justify-content:space-around">
      ${['⚡ Speed', '☁️ Cloud', '🖥 Managed'].map((t) => `<span style="color:#fff;font-size:5.5px;font-weight:700">${t}</span>`).join('')}
    </div>
  </div>`,

  // 4. Business consulting: dark with blue accents
  `<div style="width:100%;height:100%;background:#1c1c1c;font-family:system-ui;overflow:hidden">
    <div style="padding:4px 8px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #333">
      <span style="color:#fff;font-weight:700;font-size:7px">BizConsult</span>
      <div style="display:flex;gap:5px">${nav(['About', 'Services', 'Contact'], '#aaa')}</div>
    </div>
    <div style="display:flex;align-items:center;padding:10px 8px;gap:8px">
      <div style="flex:1">
        <div style="font-size:11px;font-weight:900;color:#fff;line-height:1.2">GIVE YOU THE<br><span style="color:#29b6f6">BEST BUSINESS</span><br>SOLUTIONS</div>
        <div style="font-size:6px;color:#999;margin:5px 0 6px;line-height:1.5">Professional consulting services for modern businesses.</div>
        <div style="display:flex;gap:4px">
          <div style="background:#29b6f6;color:#fff;font-size:5.5px;font-weight:700;padding:3px 8px;border-radius:2px">PURCHASE</div>
          <div style="border:1px solid #555;color:#ccc;font-size:5.5px;padding:3px 7px;border-radius:2px">READ MORE</div>
        </div>
      </div>
      <div style="width:32px;height:40px;background:#2a2a2a;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:18px">👩‍💼</div>
    </div>
    <div style="display:flex;gap:4px;padding:0 8px">
      ${[
        ['📈', 'Growth'],
        ['🎯', 'Strategy'],
        ['💡', 'Innovation'],
      ]
        .map(
          ([e, t]) =>
            `<div style="flex:1;background:#252525;border-radius:4px;padding:4px;text-align:center"><div style="font-size:9px">${e}</div><div style="font-size:5px;color:#29b6f6;font-weight:700;margin-top:1px">${t}</div></div>`,
        )
        .join('')}
    </div>
  </div>`,

  // 5. WordPress / blog: starry night
  `<div style="width:100%;height:100%;background:linear-gradient(160deg,#0a0015 0%,#1a0533 40%,#0d1a3a 100%);font-family:system-ui;overflow:hidden;position:relative">
    ${Array.from(
      { length: 12 },
      (_, i) =>
        `<div style="position:absolute;width:1.5px;height:1.5px;background:#fff;border-radius:50%;opacity:0.6;top:${(i * 17) % 80}%;left:${(i * 23) % 90}%"></div>`,
    ).join('')}
    <div style="padding:4px 8px;display:flex;justify-content:space-between;align-items:center;position:relative;z-index:2">
      <span style="color:#fff;font-weight:800;font-size:7px">🖥 WPWithTom</span>
      <div style="display:flex;gap:5px">${nav(['Features', 'Services', 'Contact'], 'rgba(255,255,255,0.7)')}</div>
    </div>
    <div style="text-align:center;padding:12px 8px 8px;position:relative;z-index:2">
      <div style="font-size:13px;font-weight:900;color:#fff;line-height:1.2;letter-spacing:-0.02em;margin-bottom:4px">LET'S MAKE<br>A WEBSITE</div>
      <div style="font-size:6.5px;color:rgba(255,255,255,0.65);margin-bottom:10px">With A Free WordPress Theme</div>
      <div style="display:flex;gap:5px;justify-content:center">
        <div style="background:#e05c35;color:#fff;font-size:5.5px;font-weight:700;padding:3px 9px;border-radius:3px">Get Started</div>
        <div style="border:1px solid rgba(255,255,255,0.4);color:#fff;font-size:5.5px;padding:3px 8px;border-radius:3px">Contact Now</div>
      </div>
    </div>
    <div style="position:absolute;bottom:8px;left:0;right:0;text-align:center;font-size:16px;z-index:2">🧍</div>
  </div>`,

  // 6. Design agency: teal / mint
  `<div style="width:100%;height:100%;background:#b2e4e0;font-family:system-ui;overflow:hidden">
    <div style="background:#fff;padding:4px 8px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #e0e0e0">
      <div><div style="border:1.5px solid #2fbfbb;width:16px;height:12px;display:inline-block;margin-right:3px"></div><span style="font-size:6.5px;font-weight:700;color:#333">state creative</span></div>
      <div style="display:flex;gap:5px">${nav(['Design', 'Portfolio', 'Contact'], '#555', 5)}</div>
      <div style="background:#2fbfbb;color:#fff;font-size:5px;font-weight:700;padding:2px 6px;border-radius:2px">REQUEST PROPOSAL</div>
    </div>
    <div style="padding:12px 10px;display:flex;align-items:center;gap:6px">
      <div style="flex:1">
        <div style="font-size:13px;font-weight:900;color:#fff;line-height:1.15;text-shadow:0 1px 4px rgba(0,0,0,0.15)">WEBSITES<br>THAT DRIVE<br>RESULTS</div>
        <div style="font-size:5.5px;color:rgba(255,255,255,0.85);margin:4px 0 6px">We design, develop &amp; maintain websites.</div>
        <div style="display:flex;align-items:center;gap:3px"><span style="font-size:5.5px;color:#fff;font-weight:600">OUR SERVICES</span><span style="color:#fff;font-size:8px">→</span></div>
      </div>
      <div style="width:35px;font-size:22px;text-align:center">👩‍💻</div>
    </div>
  </div>`,

  // 7. Landing page / digital marketing: pink gradient
  `<div style="width:100%;height:100%;background:#fff;font-family:system-ui;overflow:hidden">
    <div style="background:linear-gradient(90deg,#ff6b9d,#ff8c42);padding:2px 8px;display:flex;justify-content:space-between">
      <span style="color:#fff;font-size:5px">📞 +1-623-555-1234</span>
      <div style="background:#333;color:#fff;font-size:5px;padding:1px 5px;border-radius:2px">REQUEST CONSULT</div>
    </div>
    <div style="padding:3px 8px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee">
      <div style="display:flex;align-items:center;gap:3px">
        <div style="width:12px;height:12px;background:linear-gradient(135deg,#ff6b9d,#ff8c42);border-radius:3px"></div>
        <span style="font-weight:800;font-size:7px;color:#222">LandingPage</span>
      </div>
      <div style="display:flex;gap:6px">${nav(['Home', 'About', 'Services', 'Work'], '#555', 5)}</div>
    </div>
    <div style="background:linear-gradient(rgba(0,0,0,0.55),rgba(0,0,0,0.4)),linear-gradient(135deg,#1a1a2e,#333);padding:12px 8px 10px">
      <div style="font-size:5.5px;color:rgba(255,255,255,0.7);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px">We Are Creative</div>
      <div style="font-size:13px;font-weight:900;color:#fff;line-height:1.15;margin-bottom:4px">CREATIVE<br>DIGITAL AGENCY</div>
      <div style="font-size:5.5px;color:rgba(255,255,255,0.65);margin-bottom:7px">Industry standard dummy text since the 1500s.</div>
      <div style="display:flex;gap:4px">
        <div style="background:linear-gradient(90deg,#ff6b9d,#ff8c42);color:#fff;font-size:5.5px;font-weight:700;padding:3px 8px;border-radius:3px">READ MORE</div>
        <div style="border:1px solid #ff6b9d;color:#ff6b9d;font-size:5.5px;padding:3px 7px;border-radius:3px">REQUEST CONSULT</div>
      </div>
    </div>
  </div>`,

  // 8. SaaS / app: purple gradient
  `<div style="width:100%;height:100%;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);font-family:system-ui;overflow:hidden">
    <div style="padding:4px 8px;display:flex;justify-content:space-between;align-items:center">
      <span style="color:#fff;font-weight:900;font-size:7px">✦ AppFlow</span>
      <div style="display:flex;gap:5px">${nav(['Features', 'Pricing', 'Login'], 'rgba(255,255,255,0.8)')}</div>
    </div>
    <div style="text-align:center;padding:10px 10px 8px">
      <div style="display:inline-block;background:rgba(255,255,255,0.15);color:#fff;font-size:5.5px;padding:2px 8px;border-radius:999px;margin-bottom:5px">🚀 Now in Beta</div>
      <div style="font-size:13px;font-weight:900;color:#fff;line-height:1.15;margin-bottom:4px;letter-spacing:-0.02em">The Smarter Way<br>to Build Online</div>
      <div style="font-size:5.5px;color:rgba(255,255,255,0.75);margin-bottom:8px">No-code tools for modern businesses</div>
      <div style="display:flex;gap:5px;justify-content:center">
        <div style="background:#fff;color:#764ba2;font-size:5.5px;font-weight:800;padding:3px 9px;border-radius:999px">Start Free Trial</div>
        <div style="border:1px solid rgba(255,255,255,0.5);color:#fff;font-size:5.5px;padding:3px 8px;border-radius:999px">Watch Demo</div>
      </div>
    </div>
    <div style="display:flex;justify-content:space-around;padding:4px 8px;background:rgba(0,0,0,0.15)">
      ${['10k+ Users', '99.9% Up', '4.9★ Rated'].map((s) => `<span style="color:rgba(255,255,255,0.85);font-size:5.5px;font-weight:700">${s}</span>`).join('')}
    </div>
  </div>`,

  // 9. Restaurant: warm dark
  `<div style="width:100%;height:100%;background:#1a0a00;font-family:Georgia,serif;overflow:hidden">
    <div style="padding:4px 8px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #3d1f00">
      <span style="color:#e8a838;font-weight:700;font-size:7px;font-style:italic">🍽 La Maison</span>
      <div style="display:flex;gap:5px">${nav(['Menu', 'Reserve', 'About'], '#c9946a')}</div>
      <div style="border:1px solid #e8a838;color:#e8a838;font-size:5px;padding:2px 6px;border-radius:2px">Reserve</div>
    </div>
    <div style="padding:10px 8px;text-align:center">
      <div style="font-size:5.5px;color:#e8a838;letter-spacing:2px;text-transform:uppercase;margin-bottom:3px">Fine Dining Experience</div>
      <div style="font-size:13px;font-weight:700;color:#fff;font-style:italic;line-height:1.2;margin-bottom:5px">A Taste of<br>Excellence</div>
      <div style="font-size:6px;color:#c9946a;margin-bottom:8px">Seasonal ingredients, crafted with passion.</div>
      <div style="background:#e8a838;color:#1a0a00;font-size:6px;font-weight:700;padding:4px 12px;border-radius:2px;display:inline-block">View Our Menu</div>
    </div>
    <div style="display:flex;gap:4px;padding:0 8px">
      ${['🥗 Starters', '🥩 Mains', '🍮 Desserts']
        .map(
          (t) =>
            `<div style="flex:1;background:#2a1200;border-radius:4px;padding:4px;text-align:center"><div style="font-size:5.5px;color:#e8a838">${t}</div></div>`,
        )
        .join('')}
    </div>
  </div>`,

  // 10. Mixed corporate: light with photo
  `<div style="width:100%;height:100%;background:#f5f5f5;font-family:system-ui;overflow:hidden">
    <div style="background:#2c3e50;padding:2px 6px;display:flex;justify-content:space-between;align-items:center">
      <span style="color:#aaa;font-size:4.5px">📞 +01 258 968 5874 | Contact us | Login/Register</span>
      <div style="display:flex;gap:4px">${nav(['f', '✦', '✗', '✈'], '#aaa', 5)}</div>
    </div>
    <div style="background:#fff;padding:3px 6px;display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #3498db">
      <div style="display:flex;align-items:center;gap:3px">
        <div style="width:10px;height:10px;border:2px solid #3498db;border-radius:2px"></div>
        <div><div style="font-weight:900;font-size:6.5px;color:#333">MIXED</div><div style="font-size:4px;color:#888;letter-spacing:1px">CORPORATE LAYOUT</div></div>
      </div>
      <div style="display:flex;gap:5px">${['HOME', 'FEATURES', 'PAGES', 'PORTFOLIO'].map((n) => `<span style="color:#555;font-size:4.5px;font-weight:600">${n}</span>`).join('')}</div>
    </div>
    <div style="position:relative;overflow:hidden;height:72px">
      <img src="/assets/images/floating-bg/mixed-corporate-woman.jpg" alt="" style="position:absolute;right:0;top:0;height:100%;width:55%;object-fit:cover;object-position:center top">
      <div style="position:absolute;inset:0;background:linear-gradient(to right,#f5f5f5 45%,transparent 75%)"></div>
      <div style="position:relative;z-index:2;padding:8px 8px 0">
        <div style="font-size:11px;font-weight:900;color:#333;line-height:1.15">Clean, Modern,<br>Powerful — <span style="color:#3498db">Mixed</span></div>
        <div style="font-size:5px;color:#666;margin:3px 0 5px;line-height:1.4">Simple and clean design ready<br>for professional business.</div>
        <div style="display:flex;gap:6px">
          ${[
            ['🖥', 'Responsive'],
            ['✦', 'Retina Ready'],
            ['🏛', 'Beautiful'],
          ]
            .map(
              ([e, t]) =>
                `<div style="display:flex;align-items:center;gap:2px"><div style="width:10px;height:10px;border-radius:50%;border:1px solid #3498db;display:flex;align-items:center;justify-content:center;font-size:5px">${e}</div><span style="font-size:4.5px;color:#555">${t}</span></div>`,
            )
            .join('')}
        </div>
      </div>
    </div>
  </div>`,

  // 11. Bexar business: blue/green with photo
  `<div style="width:100%;height:100%;background:#fff;font-family:system-ui;overflow:hidden">
    <div style="background:#1a252f;padding:2px 6px;display:flex;justify-content:space-between;align-items:center">
      <span style="color:#aaa;font-size:4.5px">Connect: f ✗ g v</span>
      <div style="display:flex;gap:5px"><span style="color:#aaa;font-size:4.5px">info@bexar.com</span><span style="color:#4caf50;font-size:4.5px">Call: 123 456 5523</span></div>
    </div>
    <div style="background:#fff;padding:3px 6px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee">
      <div style="display:flex;align-items:center;gap:2px">
        <div style="width:8px;height:10px;background:linear-gradient(135deg,#4caf50,#1a8c20);clip-path:polygon(50% 0%,100% 30%,100% 70%,50% 100%,0% 70%,0% 30%)"></div>
        <span style="font-weight:900;font-size:7px;color:#333">Bexar</span>
      </div>
      <div style="display:flex;gap:5px">${['HOME', 'ABOUT', 'BLOG', 'CONTACT'].map((n) => `<span style="color:#444;font-size:4.5px;font-weight:600">${n}</span>`).join('')}</div>
      <div style="background:#4caf50;color:#fff;font-size:5px;font-weight:700;padding:2px 6px;border-radius:2px">GET STARTED</div>
    </div>
    <div style="position:relative;height:55px;overflow:hidden">
      <img src="/assets/images/floating-bg/bexar-man.jpg" alt="" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center 20%">
      <div style="position:absolute;inset:0;background:rgba(0,0,0,0.5)"></div>
      <div style="position:relative;z-index:2;padding:8px 8px">
        <div style="font-size:5px;color:rgba(255,255,255,0.8);text-transform:uppercase;letter-spacing:1px">WE ARE HERE TO</div>
        <div style="font-size:12px;font-weight:900;color:#fff;line-height:1.1">PLANNING<br>BUSINESS</div>
        <div style="border:1px solid #fff;color:#fff;font-size:5px;padding:2px 6px;border-radius:2px;display:inline-block;margin-top:4px">MORE DETAILS</div>
      </div>
    </div>
    <div style="display:flex;gap:2px;padding:3px 4px">
      ${[
        ['💎', 'BUSINESS<br>SOLUTION', '#1a252f'],
        ['📊', 'MARKET<br>RESEARCH', '#fff'],
        ['💡', 'BUSINESS<br>STRATEGY', '#fff'],
        ['🚀', 'SPEED<br>OPTIMIZATION', '#fff'],
      ]
        .map(
          ([e, t, bg]) =>
            `<div style="flex:1;background:${bg};border:${bg === '#fff' ? '1px solid #eee' : 'none'};border-radius:2px;padding:3px;text-align:center"><div style="font-size:7px">${e}</div><div style="font-size:4px;color:${bg === '#fff' ? '#333' : '#fff'};font-weight:700;line-height:1.2">${t}</div></div>`,
        )
        .join('')}
    </div>
  </div>`,

  // 12. Business solutions: dark with photo
  `<div style="width:100%;height:100%;background:#1c1c1c;font-family:system-ui;overflow:hidden;position:relative">
    <div style="padding:3px 6px;display:flex;justify-content:space-between;align-items:center;background:#111;border-bottom:1px solid #333">
      <span style="color:#888;font-size:5px">⚙</span>
      <div style="display:flex;gap:4px">${['‹', '›'].map((a) => `<div style="width:12px;height:12px;border-radius:50%;border:1px solid #555;display:flex;align-items:center;justify-content:center;color:#aaa;font-size:7px">${a}</div>`).join('')}</div>
    </div>
    <div style="position:relative;height:88px;overflow:hidden">
      <img src="/assets/images/floating-bg/business-solutions-woman.jpg" alt="" style="position:absolute;right:0;top:0;height:100%;width:50%;object-fit:cover;object-position:center top">
      <div style="position:absolute;inset:0;background:linear-gradient(to right,#1c1c1c 50%,rgba(28,28,28,0.3) 100%)"></div>
      <div style="position:relative;z-index:2;padding:10px 8px">
        <div style="font-size:5.5px;color:#aaa;text-transform:uppercase;letter-spacing:1px;margin-bottom:2px">GIVE YOU THE BEST</div>
        <div style="font-size:11px;font-weight:900;color:#fff;line-height:1.15">BUSINESS<br><span style="color:#29b6f6">SOLUTIONS</span></div>
        <div style="font-size:5px;color:#888;margin:4px 0 6px;line-height:1.5;max-width:80px">Professional services to grow your business.</div>
        <div style="display:flex;gap:4px">
          <div style="background:#29b6f6;color:#fff;font-size:5px;font-weight:700;padding:2px 7px;border-radius:2px">PURCHASE</div>
          <div style="border:1px solid #555;color:#ccc;font-size:5px;padding:2px 6px;border-radius:2px">READ MORE</div>
        </div>
      </div>
    </div>
  </div>`,

  // 13. Real estate: clean green
  `<div style="width:100%;height:100%;background:#fff;font-family:system-ui;overflow:hidden">
    <div style="background:#0d4f3c;padding:4px 8px;display:flex;justify-content:space-between;align-items:center">
      <span style="color:#fff;font-weight:800;font-size:7px">🏡 EstateHub</span>
      <div style="display:flex;gap:5px">${nav(['Buy', 'Rent', 'Sell'], 'rgba(255,255,255,0.8)')}</div>
    </div>
    <div style="background:linear-gradient(rgba(0,0,0,0.4),rgba(0,0,0,0.4)),linear-gradient(135deg,#2d6a4f,#1b4332);padding:12px 8px 10px;text-align:center">
      <div style="font-size:12px;font-weight:900;color:#fff;line-height:1.2;margin-bottom:4px">Find Your<br>Dream Home</div>
      <div style="font-size:5.5px;color:rgba(255,255,255,0.75);margin-bottom:7px">Thousands of listings across the country</div>
      <div style="display:flex;gap:3px;background:#fff;border-radius:5px;padding:3px;margin:0 4px">
        <div style="flex:1;font-size:5px;color:#aaa;padding:2px 4px">City or neighborhood...</div>
        <div style="background:#0d4f3c;color:#fff;font-size:5.5px;font-weight:700;padding:2px 7px;border-radius:3px">Search</div>
      </div>
    </div>
    <div style="display:flex;justify-content:space-around;padding:6px 4px">
      ${[
        ['🏠', 'Buy'],
        ['🔑', 'Rent'],
        ['📋', 'Sell'],
        ['📊', 'Value'],
      ]
        .map(
          ([e, t]) =>
            `<div style="text-align:center"><div style="font-size:10px">${e}</div><div style="font-size:5px;color:#0d4f3c;font-weight:700">${t}</div></div>`,
        )
        .join('')}
    </div>
  </div>`,
];
