# Bundled fonts

Drop `.ttf` / `.otf` files in this directory and they'll be auto-registered
into Qt at app startup (see `researchhq/gui/fonts.py`).

The QSS family stack expects the following — anything you don't bundle
falls back to the next family in the stack.

| Role     | Preferred                       | Fallback chain                    |
|----------|---------------------------------|-----------------------------------|
| Display  | `Geist` / `Satoshi`             | Inter → SF Pro Display → system   |
| Body     | `Inter`                         | SF Pro Text → system              |
| Mono     | `JetBrains Mono` / `Geist Mono` | SF Mono → Menlo → Consolas        |

Where to get them (all open / SIL Open Font License):
- **Geist** — https://vercel.com/font (sans + mono)
- **Inter** — https://rsms.me/inter
- **JetBrains Mono** — https://www.jetbrains.com/lp/mono/
- **Satoshi** — https://www.fontshare.com/fonts/satoshi (free)

Recommended subset to bundle (5–6 files keeps the wheel slim):

```
Geist-Regular.ttf
Geist-Medium.ttf
Geist-Bold.ttf
Inter-Regular.ttf
Inter-Medium.ttf
JetBrainsMono-Regular.ttf
```

After dropping files in this folder, rerun the app — the loader logs which
families it registered at INFO level.
