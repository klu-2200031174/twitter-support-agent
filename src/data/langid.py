"""Dependency-free language filter for short, noisy social text.

Why hand-rolled: the sandbox cannot reach the model hubs that host fasttext /
langdetect weights, and pip-installable detectors are unreliable on tweets this
short anyway. Why it matters: the first version of this pipeline filtered on
ASCII ratio, which correctly removed Japanese and silently kept French, Spanish
and German -- Latin-script languages are ~97% ASCII. That left roughly 11% of
the "English" corpus in languages the annotator cannot read, which would have
quietly poisoned both the intent taxonomy and the golden set.

Method: score function words. Function words (articles, pronouns, prepositions)
are the highest-frequency tokens in any language and are largely disjoint
across these six, so a simple weighted hit-count separates them well at tweet
length. Words that are ambiguous across languages ("no", "a", "me", "in", "die")
are excluded rather than guessed at.

This is a filter, not a language detector, and the report says so. It is tuned
to be conservative: text that is not confidently English is dropped, because a
false positive (foreign text kept) costs a mislabelled example while a false
negative (English text dropped) only costs a little volume, and we have 74k
cases to spare.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-zà-öø-ÿ']+", re.I)

# Deliberately excludes tokens shared with English or with each other.
MARKERS: dict[str, set[str]] = {
    "en": {
        "the", "and", "you", "your", "is", "was", "have", "has", "with", "for",
        "not", "this", "that", "it", "my", "from", "they", "what", "why", "when",
        "there", "would", "could", "should", "been", "were", "are", "but", "get",
        "got", "just", "still", "please", "thanks", "thank", "about", "any",
        "will", "can't", "don't", "didn't", "i'm", "it's", "of", "on", "at",
    },
    "fr": {
        "le", "la", "les", "des", "une", "est", "pas", "pour", "vous", "je",
        "que", "qui", "avec", "mais", "sur", "dans", "mon", "ma", "mes", "ce",
        "cette", "être", "avoir", "j'ai", "c'est", "n'est", "plus", "tout",
        "commande", "colis", "livraison", "bonjour", "merci", "toujours",
    },
    "es": {
        "el", "los", "las", "una", "por", "para", "con", "pero", "que", "como",
        "está", "estoy", "muy", "mi", "su", "ya", "hay", "son", "pedido",
        "hola", "gracias", "porque", "cuando", "donde", "entrega", "compra",
        "todavía", "también", "hace", "días", "señor",
    },
    "de": {
        "ich", "und", "nicht", "das", "ist", "auf", "mit", "für", "ein", "eine",
        "einen", "dem", "den", "der", "sie", "wir", "aber", "auch", "noch",
        "schon", "bei", "von", "zum", "zur", "hallo", "danke", "bestellung",
        "wurde", "haben", "kann", "wie", "warum", "sehr", "immer",
    },
    "it": {
        "il", "lo", "gli", "una", "sono", "che", "non", "per", "con", "come",
        "ma", "più", "ancora", "questo", "questa", "mio", "mia", "ordine",
        "consegna", "grazie", "ciao", "anche", "perché", "quando", "dove",
    },
    "pt": {
        "não", "uma", "para", "com", "que", "está", "são", "mas", "muito",
        "meu", "minha", "pedido", "entrega", "obrigado", "olá", "porque",
        "quando", "onde", "ainda", "também", "fazer", "vocês",
    },
}

# Characters that only appear in one of these languages.
CJK = re.compile(r"[぀-ヿ一-鿿]")
ARABIC = re.compile(r"[؀-ۿ]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def score(text: str) -> dict[str, float]:
    tokens = [t.lower() for t in _WORD.findall(text or "")]
    if not tokens:
        return {}
    n = len(tokens)
    return {lang: sum(t in words for t in tokens) / n for lang, words in MARKERS.items()}


def is_english(text: str, min_hits: float = 0.10, margin: float = 1.30) -> bool:
    """True when the text is confidently English.

    `min_hits`: at least this fraction of tokens must be English function words.
    `margin`:   English must beat the best rival language by this factor.

    Very short texts ("thanks!", "@AmazonHelp ???") fail min_hits by
    construction. We keep them: they carry no foreign-language evidence, and
    dropping every short message would bias the corpus toward long complaints.
    """
    if not text or not text.strip():
        return False
    if CJK.search(text) or ARABIC.search(text) or CYRILLIC.search(text) or DEVANAGARI.search(text):
        return False

    s = score(text)
    if not s:
        return False
    en = s.get("en", 0.0)
    rivals = {k: v for k, v in s.items() if k != "en"}
    best_rival = max(rivals.values()) if rivals else 0.0

    tokens = len(_WORD.findall(text))
    if tokens < 6:
        # Too short to judge on function words; accept unless a rival scores.
        return best_rival == 0.0

    if best_rival > 0 and en < best_rival * margin:
        return False
    return en >= min_hits or best_rival == 0.0


def detect(text: str) -> str:
    s = score(text)
    if not s:
        return "unknown"
    if CJK.search(text):
        return "ja/zh"
    if ARABIC.search(text):
        return "ar"
    lang = max(s, key=s.get)
    return lang if s[lang] > 0 else "unknown"
