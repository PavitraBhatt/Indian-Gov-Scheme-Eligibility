# SEO setup & growth checklist

The code side (structured data, sitemap, robots, FAQ, `llms.txt`) is done.
The remaining reach levers are **off-page** and mostly things only you can do
from your own accounts. Work top to bottom — the first section is the one that
most likely explains "no reach."

Replace `https://YOURDOMAIN` below with your live site URL.

---

## 1. Get indexed (do this first — free, ~10 min)

If your pages aren't in Google's index, nothing else matters. Check with:

    site:YOURDOMAIN            (paste into Google)

Few or zero results = not indexed yet. Fix it:

### Google Search Console (GSC)
1. Go to https://search.google.com/search-console and sign in.
2. Add a property → **URL prefix** → enter `https://YOURDOMAIN`.
3. Verify via the **HTML tag** method. Copy the token from the
   `google-site-verification` meta tag it gives you and set it as an env var
   on your host:

       GSC_VERIFICATION=<the token>

   (The app already injects this into the homepage `<head>` — see
   `src/scheme_checker/api.py`. Redeploy, then click **Verify**.)
4. Left menu → **Sitemaps** → submit:  `sitemap.xml`
5. Left menu → **URL Inspection** → paste your top pages one at a time →
   **Request Indexing**. Prioritise: homepage, `/schemes/`, and your 10
   most-searched schemes (PM-Kisan, Ayushman Bharat, PM Awas, etc.).

### Bing Webmaster Tools (matters for ChatGPT / Copilot)
1. https://www.bing.com/webmasters → sign in → **Import from GSC** (one click),
   or add the site and verify with the meta tag:

       BING_VERIFICATION=<the token>

2. Submit `sitemap.xml` there too.

> After this, indexing still takes days to a few weeks for a new domain.
> That wait is normal — it is not something a code change can skip.

---

## 2. Get a few real backlinks (biggest new-site lever)

A brand-new domain with zero inbound links has almost no ranking power.
You need a handful of **genuine** links. Legit, high-value options:

- **Product Hunt** / **IndieHackers** launch post.
- **GitHub**: submit to relevant "awesome" lists (awesome-india,
  awesome-civic-tech, awesome-govtech) and open-data directories.
- **Indian civic-tech directories** and NGO/govt-resource link pages.
- Ask any org/blog you know in the welfare/finance-literacy space to link.

Avoid: bought links, link exchanges, PBNs, comment/forum-signature spam.
Google's spam systems detect these and can **deindex or penalise** the domain —
strictly worse than being new.

---

## 3. Distribution — go where the users already ask

Referral traffic from real people is also a trust signal to Google.
Answer real questions ("am I eligible for X?", "documents for Y") and link
where genuinely helpful:

- Reddit: r/india, r/personalfinanceindia, state subreddits
- Quora (India government-scheme topics)
- Facebook / WhatsApp community groups
- Regional-language YouTube creators who explain schemes

Be helpful first, link second. Drive-by link drops get removed and hurt trust.

---

## 4. Content: win the long tail, not the head terms

You will not outrank `myscheme.gov.in` for "government schemes". You *can* rank
for specific, low-competition questions. Each scheme page now targets these via
its FAQ. Keep expanding on that axis:

- More schemes + more states = more unique pages ranking for
  "[scheme] eligibility [year]", "[scheme] documents required",
  "[scheme] in [state]".
- Keep the answer text specific and genuinely useful (Google rewards this;
  AI answer engines quote it).

---

## Quick monthly check

- GSC → **Performance**: which queries/pages get impressions & clicks? Do more
  of what's working.
- GSC → **Pages**: fix anything under "Not indexed".
- Re-submit sitemap after adding schemes/states.
