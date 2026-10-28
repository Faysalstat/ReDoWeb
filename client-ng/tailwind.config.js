/** @type {import('tailwindcss').Config} */
// From docs/ANGULAR_UI_BLUEPRINT.md section 1.2. @angular/build finds this file and
// runs Tailwind 3 + autoprefixer itself, so there is no postcss config.
module.exports = {
  darkMode: ['class'],
  // The copied admin panel uses its own classic class names; keep Tailwind from
  // generating same-named utilities (.table, .grayscale, .text-muted…) for it.
  content: ['./src/**/*.{html,ts}', '!./src/app/admin/**'],
  theme: {
    extend: {
      fontFamily: {
        inter: ['var(--font-inter)'],
        display: ['var(--font-display)'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
        popover: { DEFAULT: 'hsl(var(--popover))', foreground: 'hsl(var(--popover-foreground))' },
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary: { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        chart: {
          1: 'hsl(var(--chart-1))', 2: 'hsl(var(--chart-2))', 3: 'hsl(var(--chart-3))',
          4: 'hsl(var(--chart-4))', 5: 'hsl(var(--chart-5))',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
      },
      keyframes: {
        'glow-flash': {
          '0%, 100%': { boxShadow: '0 0 40px 12px rgba(34,197,94,0.15), inset 0 0 20px rgba(34,197,94,0.08)' },
          '50%': { boxShadow: '0 0 60px 20px rgba(34,197,94,0.3), inset 0 0 30px rgba(34,197,94,0.15)' },
        },
        'blink-green': {
          '0%, 100%': { boxShadow: '0 0 15px rgba(34,197,94,0.5), inset 0 0 15px rgba(34,197,94,0.1)', borderColor: 'rgba(34,197,94,0.6)' },
          '50%': { boxShadow: '0 0 30px rgba(34,197,94,1), inset 0 0 30px rgba(34,197,94,0.3)', borderColor: 'rgba(34,197,94,1)' },
        },
        marquee: { from: { transform: 'translateX(0)' }, to: { transform: 'translateX(-50%)' } },
        'bar-sweep': { '0%, 100%': { width: '20%' }, '50%': { width: '90%' } },
      },
      animation: {
        'glow-flash': 'glow-flash 2s ease-in-out infinite',
        'blink-green': 'blink-green 1.5s infinite',
        marquee: 'marquee 30s linear infinite',
        'bar-sweep': 'bar-sweep 2s ease-in-out infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
