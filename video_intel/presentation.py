"""Offline report design tokens and bilingual interface vocabulary."""

VERDICTS = ("false", "mostly-false", "half-true", "mostly-true", "true",
            "not-enough-evidence", "not-checkable", "not-checked")

# Keys are stable data identifiers; only interface copy is translated.
LABELS = {
    "en": {
        "report": "Video analysis", "comparison": "Video comparison", "contents": "Contents",
        "toc": "Table of contents", "copy": "Copy as Markdown", "print": "Print",
        "copied": "Markdown copied", "copy_failed": "Copy unavailable. Open the adjacent Markdown file.",
        "markdown": "Report Markdown", "watch": "Watch source", "channel": "Creator",
        "unknown_channel": "Unknown creator", "transcript": "Transcript", "details": "Video details",
        "summary": "Summary", "moments": "Key moments", "claims": "Claims", "caveats": "Caveats",
        "steps": "Steps", "mentions": "Mentions", "hook": "Hook and retention",
        "sources": "Cited sources", "tone": "Tone and persuasion", "actions": "Actions",
        "audience": "Audience", "frames": "Frames", "frame_at": "Frame at",
        "verdict_summary": "Verdict summary", "verdict": "Verdict", "all_verdicts": "All verdicts",
        "search_claims": "Search claims", "search_hint": "Search text, evidence or rationale",
        "count": "{visible} of {total} claims", "empty": "No claims match these filters.",
        "search_transcript": "Search transcript", "show_transcript": "Read full transcript",
        "segments": "segments", "confidence": "Confidence", "rating": "Rating",
        "unrated": "Not rated", "published": "Published", "retrieved": "Retrieved",
        "asr_model": "ASR model", "source": "Source", "unknown": "Unknown",
        "asr_caveat": "Machine transcription may distort names and numbers; check the source audio.",
        "captions-manual": "Manual captions", "captions-auto": "Automatic captions",
        "asr": "Machine transcription", "none": "No transcript",
        "false": "False", "mostly-false": "Mostly false", "half-true": "Half true",
        "mostly-true": "Mostly true", "true": "True", "not-enough-evidence": "Not enough evidence",
        "not-checkable": "Not checkable", "not-checked": "Not checked",
        "fact": "Fact", "opinion": "Opinion", "prediction": "Prediction", "advice": "Advice",
        "low": "Low", "medium": "Medium", "high": "High",
        "videos": "Videos", "common_claims": "Common claims", "contradictions": "Contradictions",
        "who_says_what": "Who says what", "unique_points": "Unique points", "overall": "Overall verdict",
        "note": "Note", "resolution": "Resolution", "supports": "Supports", "opposes": "Opposes",
        "mixed": "Mixed", "silent": "Silent", "unclear": "Unclear",
        "prerequisites": "Prerequisites", "tools": "Tools", "warning": "Warning", "outcome": "Outcome",
        "verified": "Verified", "unverified": "Unverified", "official": "Official source",
        "specificity": "Specificity", "found": "Found", "priority": "Priority", "effort": "Effort",
        "depends_on": "Depends on", "shifts": "Tone shifts", "techniques": "Persuasion techniques",
        "bias_signals": "Bias signals", "disclosure": "Disclosure", "sponsored": "Sponsored",
        "affiliate": "Affiliate", "disclosed": "Disclosed", "opening": "Opening hook",
        "spoken": "Spoken", "on_screen": "On screen", "structure": "Structure", "ends": "Ends",
        "pacing": "Pacing", "duration": "Duration", "cuts": "Cuts/10s", "wpm": "Words/minute",
        "on_screen_text": "On-screen text", "retention": "Retention tactics", "why_it_works": "Why it works",
        "template": "Reusable template", "length": "Length", "example": "Example", "weaknesses": "Weaknesses",
        "yes": "Yes", "no": "No", "partly": "Partly", "likely": "Likely", "named": "Named", "vague": "Vague",
        "upload_date": "Upload date", "view_count": "Views", "like_count": "Likes",
        "description": "Description", "platform": "Platform",
    },
    "tr": {
        "report": "Video analizi", "comparison": "Video karşılaştırması", "contents": "İçindekiler",
        "toc": "İçindekiler", "copy": "Markdown olarak kopyala", "print": "Yazdır",
        "copied": "Markdown kopyalandı", "copy_failed": "Kopyalanamadı. Yanındaki Markdown dosyasını açın.",
        "markdown": "Raporun Markdown metni", "watch": "Kaynağı izle", "channel": "İçerik üreticisi",
        "unknown_channel": "Bilinmeyen içerik üreticisi", "transcript": "Transkript", "details": "Video ayrıntıları",
        "summary": "Özet", "moments": "Önemli anlar", "claims": "İddialar", "caveats": "Uyarılar",
        "steps": "Adımlar", "mentions": "Geçenler", "hook": "Hook analizi", "sources": "Kaynaklar",
        "tone": "Ton", "actions": "Yapılacaklar", "audience": "Hedef kitle", "frames": "Kareler",
        "frame_at": "Video karesi", "verdict_summary": "Doğruluk dağılımı", "verdict": "Sonuç",
        "all_verdicts": "Tüm sonuçlar", "search_claims": "İddialarda ara",
        "search_hint": "Metin, kanıt veya gerekçede ara", "count": "{total} iddiadan {visible} tanesi",
        "empty": "Bu filtrelerle eşleşen iddia yok.", "search_transcript": "Transkriptte ara",
        "show_transcript": "Transkriptin tamamını oku", "segments": "bölüm", "confidence": "Güven",
        "rating": "Puan", "unrated": "Puanlanmadı", "published": "Yayın", "retrieved": "Erişim",
        "asr_model": "ASR modeli", "source": "Kaynak", "unknown": "Bilinmiyor",
        "asr_caveat": "Otomatik ses çözümlemesi adları ve sayıları yanlış aktarabilir; kaynak sesi kontrol edin.",
        "captions-manual": "Elle hazırlanan altyazı", "captions-auto": "Otomatik altyazı",
        "asr": "Otomatik ses çözümlemesi", "none": "Transkript yok",
        "false": "Yanlış", "mostly-false": "Çoğunlukla yanlış", "half-true": "Yarı doğru",
        "mostly-true": "Çoğunlukla doğru", "true": "Doğru", "not-enough-evidence": "Yeterli kanıt yok",
        "not-checkable": "Kontrol edilemez", "not-checked": "Kontrol edilmedi",
        "fact": "Olgu", "opinion": "Görüş", "prediction": "Öngörü", "advice": "Tavsiye",
        "low": "Düşük", "medium": "Orta", "high": "Yüksek",
        "videos": "Videolar", "common_claims": "Ortak iddialar", "contradictions": "Çelişkiler",
        "who_says_what": "Kim ne diyor", "unique_points": "Farklı noktalar", "overall": "Genel değerlendirme",
        "note": "Not", "resolution": "Değerlendirme", "supports": "Destekliyor", "opposes": "Karşı çıkıyor",
        "mixed": "Karma", "silent": "Değinmiyor", "unclear": "Belirsiz",
        "prerequisites": "Ön koşullar", "tools": "Araçlar", "warning": "Uyarı", "outcome": "Sonuç",
        "verified": "Doğrulandı", "unverified": "Doğrulanmadı", "official": "Resmî kaynak",
        "specificity": "Açıklık", "found": "Bulundu", "priority": "Öncelik", "effort": "Çaba",
        "depends_on": "Bağlı olduğu adım", "shifts": "Ton değişimleri", "techniques": "İkna teknikleri",
        "bias_signals": "Yanlılık işaretleri", "disclosure": "Ticari ilişkiler", "sponsored": "Sponsorlu",
        "affiliate": "Satış ortaklığı", "disclosed": "Açıklandı", "opening": "Açılış hook'u",
        "spoken": "Söylenen", "on_screen": "Ekranda", "structure": "Yapı", "ends": "Bitiş",
        "pacing": "Tempo", "duration": "Süre", "cuts": "10 saniyedeki kesme", "wpm": "Dakikadaki kelime",
        "on_screen_text": "Ekran yazıları", "retention": "İzleyiciyi tutma teknikleri",
        "why_it_works": "Neden işe yarıyor", "template": "Tekrar kullanılabilir şablon", "length": "Uzunluk",
        "example": "Örnek", "weaknesses": "Zayıf noktalar", "yes": "Evet", "no": "Hayır",
        "partly": "Kısmen", "likely": "Muhtemelen", "named": "Açıkça belirtilmiş", "vague": "Muğlak",
        "upload_date": "Yükleme tarihi", "view_count": "İzlenme", "like_count": "Beğeni",
        "description": "Açıklama", "platform": "Platform",
    },
}

_ENUM_TR = {
    "person": "Kişi", "product": "Ürün", "tool": "Araç", "company": "Şirket", "book": "Kitap",
    "link": "Bağlantı", "other": "Diğer", "positive": "Olumlu", "neutral": "Nötr", "negative": "Olumsuz",
    "ad": "Reklam", "minutes": "Dakikalar", "hours": "Saatler", "days": "Günler",
    "scarcity": "Kıtlık", "urgency": "Aciliyet", "social-proof": "Sosyal kanıt", "authority": "Otorite",
    "fear": "Korku", "anecdote": "Anekdot", "false-dichotomy": "Sahte ikilem",
    "emotional-appeal": "Duygulara seslenme", "flattery": "Övgü",
    "question": "Soru", "surprise": "Sürpriz", "promise": "Vaat", "problem": "Sorun",
    "result": "Sonuç", "story": "Hikâye", "challenge": "Meydan okuma", "visual": "Görsel",
    "setup": "Hazırlık", "payoff": "Karşılık", "cta": "Eylem çağrısı", "body": "Gövde",
    "intro": "Giriş", "outro": "Kapanış", "caption": "Altyazı", "label": "Etiket",
    "bold-claim": "İddialı açılış", "pattern-interrupt": "Beklentiyi kırma", "story-open": "Hikâyeyle açılış",
    "result-first": "Önce sonuç", "curiosity-gap": "Merak boşluğu", "value": "Fayda", "proof": "Kanıt", "loop": "Döngü", "watermark": "Filigran",
}
LABELS["tr"].update(_ENUM_TR)
LABELS["en"].update({key: key.replace("-", " ").capitalize() for key in _ENUM_TR})


def label(key, language="en"):
    if isinstance(key, bool):
        key = "yes" if key else "no"
    if key is None:
        key = "unknown"
    return LABELS[language].get(key, LABELS["en"].get(key, str(key)))


def report_language(data, transcript=None):
    explicit = data.get("report_language")
    fallback = (transcript or {}).get("language")
    return (explicit if isinstance(explicit, str) and explicit in LABELS
            else fallback if isinstance(fallback, str) and fallback in LABELS else "en")


def platform_name(platform):
    return {"youtube": "YouTube", "instagram": "Instagram", "x": "X", "tiktok": "TikTok"}.get(
        platform.casefold(), platform.title())


CSS = """
:root { color-scheme:light dark; --bg:#f5f6f8; --surface:#fff; --ink:#19232d;
 --muted:#526170; --line:#d4dbe2; --accent:#1558a6; --false:#c62828;
 --mostly-false:#e65100; --half-true:#f9a825; --mostly-true:#7cb342; --true:#2e7d32;
 --not-enough-evidence:#546e7a; --not-checkable:#757575; --not-checked:#757575;
 --mostly-false-text:#b33e00; --half-true-text:#795500; --mostly-true-text:#3f6b18;
 --not-checkable-text:#707070; --not-checked-text:#707070; --segment-ink:#fff; }
@media(prefers-color-scheme:dark) { :root { --bg:#14191e; --surface:#1c232a; --ink:#edf1f5;
 --muted:#b1beca; --line:#3e4b58; --accent:#91c3ff; --false:#ff9588;
 --mostly-false:#ffb076; --half-true:#e8ca6a; --mostly-true:#b9d77b; --true:#7fd5a5;
 --not-enough-evidence:#adbed0; --not-checkable:#b6bbc2; --not-checked:#b6bbc2;
 --mostly-false-text:var(--mostly-false); --half-true-text:var(--half-true);
 --mostly-true-text:var(--mostly-true); --not-checkable-text:var(--not-checkable);
 --not-checked-text:var(--not-checked); --segment-ink:#14191e; } }
* { box-sizing:border-box; } body { margin:0; background:var(--bg); color:var(--ink);
 font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }
.layout { max-width:1080px; margin:auto; padding:36px 28px 80px; display:grid;
 grid-template-columns:260px minmax(0,720px); gap:0 44px; }
.report-header { grid-column:2; padding:0 0 28px; border-bottom:1px solid var(--line); }
.rail { grid-column:1; grid-row:1 / 3; position:sticky; top:24px; align-self:start;
 max-height:calc(100dvh - 48px); overflow:auto; padding-right:8px; }
main { grid-column:2; } main,section,article,details,.report-header,.rail { min-width:0; overflow-wrap:anywhere; }
h1,h2,h3 { font-family:ui-serif,"New York",Georgia,serif; font-weight:650; }
h1 { font-size:40px; line-height:1.14; letter-spacing:-.025em; margin:16px 0 20px; }
h2 { font-size:28px; line-height:1.25; margin:0 0 20px; }
h3 { font-size:20px; line-height:1.35; margin:12px 0; }
section { margin-top:40px; scroll-margin-top:24px; } #claim-list { scroll-margin-top:24px; } p { margin:12px 0; }
a { color:var(--accent); text-underline-offset:3px; display:inline-block; min-height:44px;
 min-width:44px; padding-block:8px; vertical-align:baseline; max-width:100%; }
:focus-visible { outline:3px solid var(--accent); outline-offset:3px; }
button,input,select { font:inherit; min-height:44px; min-width:44px; max-width:100%;
 border:1px solid var(--line); border-radius:6px; padding:8px 12px; background:var(--surface); color:var(--ink); }
button { cursor:pointer; } button:hover { border-color:var(--accent); }
button[aria-pressed=true] { outline:2px solid var(--accent); outline-offset:2px; }
.muted,dt,.meta { color:var(--muted); } .meta { display:flex; flex-wrap:wrap; gap:0 12px; font-size:14px; }
.chip { display:inline-block; border:1px solid var(--line); border-radius:6px; padding:3px 9px; font-size:14px; }
.source-row { display:flex; flex-wrap:wrap; align-items:center; gap:6px 16px; }
.source-caveat { font-size:14px; color:var(--muted); }
.toc h2,.rail h2 { font:600 14px/1.5 system-ui,sans-serif; color:var(--muted); margin:0 0 8px; }
.toc ul { list-style:none; padding:0; margin:0; }
.toc li { margin:0; } .toc a { display:block; padding:8px 12px; border-left:3px solid transparent;
 text-decoration:none; color:var(--muted); }
.toc a[aria-current=true] { color:var(--accent); border-color:var(--accent); background:var(--surface); }
.actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:24px; }
.rail .actions { flex-direction:column; } .mobile-actions { display:none; }
#copy-status { display:block; font-size:14px; color:var(--muted); margin-top:8px; }
.verdict-summary { margin-top:24px; } .verdict-summary h2 { font:600 14px/1.5 system-ui,sans-serif; margin:0 0 10px; }
.verdict-scroll { overflow-x:auto; padding:4px; margin-inline:-4px; }
.verdict-bar { display:flex; gap:3px; width:100%; min-height:44px; }
.verdict-segment { flex:var(--count) 1 0%; min-width:44px; padding:0; border:0; border-radius:0;
 background:var(--verdict); color:var(--segment-ink); font-weight:700; }
.verdict-segment:is([data-filter-verdict=mostly-false],[data-filter-verdict=half-true],
 [data-filter-verdict=mostly-true]) { color:#111; }
.verdict-legend { display:flex; flex-wrap:wrap; gap:4px 12px; margin-top:10px; }
.verdict-legend button { background:transparent; border:0; display:flex; gap:8px; align-items:center;
 padding:6px 2px; font-size:14px; text-align:left; }
.swatch { width:10px; height:10px; border-radius:50%; background:var(--verdict); flex:none; }
.controls { display:flex; flex-wrap:wrap; gap:12px; margin:16px 0; align-items:end; }
.controls label { display:grid; gap:6px; flex:1 1 200px; font-size:14px; min-width:0; }
.controls input,.controls select { width:100%; } #claim-count { display:block; width:100%; color:var(--muted); font-size:14px; }
article { border:1px solid var(--line); border-radius:6px; background:var(--surface); padding:22px; margin:16px 0; }
[data-claim] { border-left:4px solid var(--verdict); }
.claim-verdict { color:var(--verdict-text); display:flex; align-items:center; flex-wrap:wrap; gap:10px; font-size:14px; font-weight:700; }
.truth-meter { display:inline-flex; gap:4px; } .truth-meter i { display:block; width:9px; height:9px;
 border:1.5px solid currentColor; border-radius:50%; } .truth-meter .filled { background:currentColor; }
.claim-meta { color:var(--muted); font-size:14px; margin:0; }
blockquote { margin:16px 0; padding:2px 16px; border-left:2px solid var(--line); color:var(--muted); }
ul,ol { padding-left:24px; } li { margin:8px 0; } dl { margin:12px 0; } dt { font-weight:600; }
dd { margin:0 0 16px; } dd dl,dd ul { padding-left:16px; }
.time { font:14px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace; white-space:nowrap; }
.moment { display:grid; grid-template-columns:64px minmax(0,1fr); gap:16px; padding:12px 0;
 border-bottom:1px solid var(--line); } .moment h3 { margin:8px 0; } .moment p { margin:0 0 8px; }
.evidence { list-style:none; padding:0; margin:20px 0 0; border-top:1px solid var(--line); font-size:14px; }
.evidence li { margin:12px 0 0; } .evidence p { margin:0; } .evidence strong { font-weight:650; }
summary { cursor:pointer; padding:12px 0; min-height:44px; font-weight:600; }
.transcript-search { display:grid; gap:8px; margin:16px 0; font-size:14px; }
.transcript p { margin:0; padding:4px 0; } .transcript .time { margin-right:8px; }
.frame-strip { display:flex; gap:16px; overflow-x:auto; padding-bottom:12px; }
.frame-strip img { aspect-ratio:16/9; object-fit:contain; background:var(--bg); }
figure { margin:0; flex:0 0 240px; min-width:0; } img { display:block; max-width:100%; width:100%; height:auto; border-radius:6px; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; background:var(--bg); padding:12px; border-radius:6px; }
code { font-size:.9em; } [hidden] { display:none!important; }
@media(max-width:1023px) {
 .layout { display:flex; flex-direction:column; max-width:776px; padding:28px 28px 60px; }
 .report-header { order:0; } .rail { order:1; position:sticky; top:0; z-index:2; padding:0;
   margin:0 -28px; max-height:none; background:var(--bg); overflow:visible; }
 main { order:2; } .toc h2,.rail .actions { display:none; }
 .toc ul { display:flex; overflow-x:auto; gap:4px; padding:8px 28px; }
 .toc li { flex:none; } .toc a { white-space:nowrap; border:1px solid var(--line); border-radius:6px; padding:8px 12px; }
 .toc a[aria-current=true] { border-color:var(--accent); } .mobile-actions { display:flex; }
 section,#claim-list { scroll-margin-top:88px; } h1 { font-size:30px; } h2 { font-size:30px; } h3 { font-size:22px; }
 body { font-size:17px; } .meta,.chip,.claim-meta,.claim-verdict,.time,.evidence,.controls label { font-size:15px; }
}
@media(max-width:480px) { .layout { padding:24px 16px 48px; } article { padding:16px; }
 .rail { margin:0 -16px; } .toc ul { padding-inline:16px; } .moment { gap:12px; }
 .mobile-actions button { flex:1 1 auto; font-size:15px; } .verdict-legend { gap:2px 10px; }
}
@media(prefers-reduced-motion:reduce) { *,*::before,*::after { scroll-behavior:auto!important;
 animation:none!important; transition:none!important; } }
@media print {
 :root { color-scheme:light; --bg:#fff; --surface:#fff; --ink:#000; --muted:#333; --line:#aaa;
 --accent:#000; --false:#962b20; --mostly-false:#8a400f; --half-true:#725400;
 --mostly-true:#465e17; --true:#125532; --not-enough-evidence:#455668; --not-checkable:#555; --not-checked:#555; }
 .layout { display:block; max-width:none; padding:0; } .rail,.actions,.controls,button,#copy-status,
 .transcript-search,.verdict-scroll { display:none!important; } article,figure { break-inside:avoid; }
 [data-claim][hidden],[data-transcript-segment][hidden] { display:block!important; }
 a { min-height:0; min-width:0; padding:0; } .frame-strip { flex-wrap:wrap; overflow:visible; }
 .truth-meter,.swatch,.verdict-segment { print-color-adjust:exact; } section { margin-top:24px; }
 .verdict-legend button { display:flex!important; min-height:0; padding:0; }
}
"""

SCRIPT = """
(() => {
  const root = document.documentElement;
  const search = document.getElementById('claim-search');
  const verdict = document.getElementById('claim-verdict');
  const cards = Array.from(document.querySelectorAll('[data-claim]'));
  const buttons = document.querySelectorAll('[data-filter-verdict]');
  function filterClaims() {
    if (!search || !verdict) return;
    const query = search.value.toLocaleLowerCase(root.lang);
    let visible = 0;
    cards.forEach(card => {
      card.hidden = !(card.textContent.toLocaleLowerCase(root.lang).includes(query) &&
        (!verdict.value || card.dataset.verdict === verdict.value));
      if (!card.hidden) visible++;
    });
    document.getElementById('claim-count').textContent = root.dataset.count
      .replace('{visible}', visible).replace('{total}', cards.length);
    document.getElementById('claim-empty').hidden = visible !== 0;
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filterVerdict === verdict.value)));
  }
  if (search && verdict) {
    search.addEventListener('input', filterClaims);
    verdict.addEventListener('change', filterClaims);
    buttons.forEach(button => button.addEventListener('click', () => {
      verdict.value = verdict.value === button.dataset.filterVerdict ? '' : button.dataset.filterVerdict;
      filterClaims();
      document.getElementById('claim-list').scrollIntoView({block:'start'});
    }));
    filterClaims();
  }
  const transcriptSearch = document.getElementById('transcript-search');
  if (transcriptSearch) transcriptSearch.addEventListener('input', () => {
    const query = transcriptSearch.value.toLocaleLowerCase(root.lang);
    document.querySelectorAll('[data-transcript-segment]').forEach(segment => {
      segment.hidden = !segment.textContent.toLocaleLowerCase(root.lang).includes(query);
    });
  });
  const tocLinks = Array.from(document.querySelectorAll('.toc a'));
  const tocSections = tocLinks.map(link => document.getElementById(link.hash.slice(1)));
  let activeLink;
  function updateActiveSection() {
    let current = 0;
    if (window.scrollY > 0) tocSections.forEach((section, index) => {
      if (section && section.getBoundingClientRect().top <= window.innerHeight * .3) current = index;
    });
    const link = tocLinks[current];
    if (!link) return;
    if (link !== activeLink) {
      tocLinks.forEach(item => item.setAttribute('aria-current', String(item === link)));
      activeLink = link;
    }
    if (window.matchMedia('(max-width:1023px)').matches) {
      const row = link.closest('ul');
      const chip = link.getBoundingClientRect();
      const bounds = row.getBoundingClientRect();
      if (chip.left < bounds.left || chip.right > bounds.right) {
        row.scrollBy({left: chip.left - bounds.left - (bounds.width - chip.width) / 2, behavior:'auto'});
      }
    }
  }
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(updateActiveSection);
    tocSections.forEach(section => { if (section) observer.observe(section); });
  }
  let tocFramePending = false;
  function scheduleTocUpdate() {
    if (tocFramePending) return;
    tocFramePending = true;
    requestAnimationFrame(() => { tocFramePending = false; updateActiveSection(); });
  }
  addEventListener('scroll', scheduleTocUpdate, {passive:true});
  addEventListener('resize', scheduleTocUpdate);
  updateActiveSection();
  document.querySelectorAll('[data-copy-markdown]').forEach(button => button.addEventListener('click', async () => {
    const active = document.activeElement;
    const text = document.getElementById('markdown-source');
    const status = document.getElementById('copy-status');
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text.value);
      else {
        text.hidden = false;
        text.select();
        const copied = document.execCommand('copy');
        text.hidden = true;
        if (!copied) throw new Error('copy unavailable');
      }
      status.textContent = root.dataset.copied;
    } catch (_) {
      text.hidden = true;
      status.textContent = root.dataset.copyFailed;
    } finally { if (active) active.focus({preventScroll:true}); }
  }));
  document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => window.print()));
  let transcriptWasOpen = false;
  addEventListener('beforeprint', () => {
    const transcript = document.getElementById('full-transcript');
    if (transcript) { transcriptWasOpen = transcript.open; transcript.open = true; }
  });
  addEventListener('afterprint', () => {
    const transcript = document.getElementById('full-transcript');
    if (transcript) transcript.open = transcriptWasOpen;
  });
})();
"""
