"""Fabrication guard: check a tailored resume only contains facts present in the original.

Hard errors (-> rejected): new employer/title/dates, new degree/institution, new project, new skill,
new technology, numbers/metrics that never appeared in the original entry.
Warnings (-> flagged): bullets or achievements that share too little wording with any original text.
"""

import re

from app.schemas.candidate import CandidateProfile, EducationEntry, ExperienceEntry, ProjectEntry
from app.schemas.resume import TailoredResume, VerificationIssue, VerificationResult
from app.services.normalization import normalize_text

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "on", "at", "by", "as", "is", "was",
    "were", "are", "be", "from", "that", "this", "it", "its", "into", "using", "used", "via", "across",
    "while", "which", "our", "their", "we", "i", "my", "over", "under", "per", "than", "more", "up",
}
BULLET_OVERLAP_THRESHOLD = 0.5
FREE_TEXT_OVERLAP_THRESHOLD = 0.6


def _tokens(s: str | None) -> set[str]:
    return {t for t in normalize_text(s).split() if t not in _STOPWORDS and len(t) > 1}


def _numbers(s: str | None) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(s or "")}


def _norm(s: str | None) -> str:
    return normalize_text(s)


def _overlap(candidate: str, sources: list[str]) -> float:
    ct = _tokens(candidate)
    if not ct:
        return 1.0
    best = 0.0
    for src in sources:
        st = _tokens(src)
        if st:
            best = max(best, len(ct & st) / len(ct))
    return best


def _entry_text(e: ExperienceEntry | ProjectEntry | EducationEntry) -> str:
    return " ".join(str(v) for v in e.model_dump().values() if v)


class _Checker:
    def __init__(self, original: CandidateProfile, raw_text: str):
        self.original = original
        self.raw_norm = _norm(raw_text)
        self.raw_numbers = _numbers(raw_text)
        self.issues: list[VerificationIssue] = []
        self.original_skill_set = {_norm(s) for s in original.skills}
        self.original_tech_set = {_norm(t) for p in original.projects for t in p.technologies}

    def error(self, section: str, message: str) -> None:
        self.issues.append(VerificationIssue(severity="error", section=section, message=message))

    def warn(self, section: str, message: str) -> None:
        self.issues.append(VerificationIssue(severity="warning", section=section, message=message))

    def in_original_text(self, s: str | None) -> bool:
        n = _norm(s)
        return bool(n) and n in self.raw_norm

    # --- sections -------------------------------------------------------

    def check_contact(self, t: TailoredResume) -> None:
        for field in ("full_name", "email", "phone", "location"):
            val = getattr(t, field)
            orig = getattr(self.original, field)
            if val and _norm(val) != _norm(orig) and not self.in_original_text(val):
                self.error("contact", f"{field} '{val}' is not in the original resume")

    def check_skills(self, t: TailoredResume) -> None:
        for skill in t.skills:
            n = _norm(skill)
            if n and n not in self.original_skill_set and n not in self.original_tech_set and n not in self.raw_norm:
                self.error("skills", f"Skill '{skill}' does not appear in the original resume")

    def check_experience(self, t: TailoredResume) -> None:
        originals = {(_norm(e.company), _norm(e.title)): e for e in self.original.experience}
        if len(t.experience) > len(self.original.experience):
            self.error("experience", "Tailored resume has more experience entries than the original")
        for e in t.experience:
            orig = originals.get((_norm(e.company), _norm(e.title)))
            if orig is None:
                self.error("experience", f"Experience '{e.title} at {e.company}' is not in the original resume")
                continue
            self._check_dates("experience", f"{e.title} at {e.company}", e, orig)
            if e.location and _norm(e.location) != _norm(orig.location) and not self.in_original_text(e.location):
                self.error("experience", f"Location '{e.location}' for {e.company} is not in the original")
            self._check_bullets(f"experience:{e.company}", e.bullets, orig.bullets, _entry_text(orig))

    def check_education(self, t: TailoredResume) -> None:
        if len(t.education) > len(self.original.education):
            self.error("education", "Tailored resume has more education entries than the original")
        for ed in t.education:
            match = next((o for o in self.original.education if _norm(o.institution) == _norm(ed.institution)), None)
            if match is None:
                self.error("education", f"Institution '{ed.institution}' is not in the original resume")
                continue
            for field in ("degree", "field_of_study"):
                val = getattr(ed, field)
                if val and _norm(val) != _norm(getattr(match, field)) and not self.in_original_text(val):
                    self.error("education", f"{field} '{val}' for {ed.institution} is not in the original")
            self._check_dates("education", ed.institution, ed, match)
            self._check_bullets(f"education:{ed.institution}", ed.details, match.details, _entry_text(match))

    def check_projects(self, t: TailoredResume) -> None:
        if len(t.projects) > len(self.original.projects):
            self.error("projects", "Tailored resume has more projects than the original")
        for p in t.projects:
            match = next((o for o in self.original.projects if _norm(o.name) == _norm(p.name)), None)
            if match is None:
                self.error("projects", f"Project '{p.name}' is not in the original resume")
                continue
            for tech in p.technologies:
                n = _norm(tech)
                if n and n not in {_norm(x) for x in match.technologies} and n not in self.original_skill_set \
                        and n not in self.raw_norm:
                    self.error("projects", f"Technology '{tech}' on project '{p.name}' is not in the original")
            sources = [*match.bullets, match.description or ""]
            self._check_bullets(f"projects:{p.name}", p.bullets, sources, _entry_text(match))
            if p.description and _overlap(p.description, sources) < BULLET_OVERLAP_THRESHOLD:
                self.warn("projects", f"Description of '{p.name}' shares little wording with the original")
            self._check_numbers(f"projects:{p.name}", p.description, _entry_text(match))

    def check_free_lists(self, t: TailoredResume) -> None:
        for section, items, originals in (
            ("achievements", t.achievements, self.original.achievements),
            ("certifications", t.certifications, self.original.certifications),
        ):
            for item in items:
                if _norm(item) in {_norm(o) for o in originals} or self.in_original_text(item):
                    continue
                if section == "certifications":
                    self.error(section, f"Certification '{item}' is not in the original resume")
                elif _overlap(item, originals + [self.raw_norm]) < FREE_TEXT_OVERLAP_THRESHOLD:
                    self.warn(section, f"Achievement '{item}' shares little wording with the original")
                self._check_numbers(section, item, None)

    def check_summary(self, t: TailoredResume) -> None:
        # The summary is free prose; only numbers/metrics are hard-checked against the original.
        if t.summary:
            self._check_numbers("summary", t.summary, None)

    # --- helpers --------------------------------------------------------

    def _check_dates(self, section: str, label: str, new, orig) -> None:
        for field in ("start_date", "end_date"):
            val = getattr(new, field)
            ov = getattr(orig, field)
            if val and _norm(val) != _norm(ov) and not self.in_original_text(val):
                self.error(section, f"{field} '{val}' for {label} differs from the original ('{ov}')")

    def _check_bullets(self, section: str, bullets: list[str], orig_bullets: list[str], orig_text: str) -> None:
        if len(bullets) > max(len(orig_bullets), 1):
            self.warn(section, "More bullets than the original entry")
        for b in bullets:
            self._check_numbers(section, b, orig_text)
            if _overlap(b, orig_bullets + [orig_text]) < BULLET_OVERLAP_THRESHOLD:
                self.warn(section, f"Bullet shares little wording with the original: '{b[:80]}'")

    def _check_numbers(self, section: str, text: str | None, orig_text: str | None) -> None:
        allowed = _numbers(orig_text) if orig_text else self.raw_numbers
        allowed = allowed | self.raw_numbers
        for n in _numbers(text):
            if n not in allowed:
                self.error(section, f"Number '{n}' in '{(text or '')[:60]}' does not appear in the original")


def verify_tailored_resume(original: CandidateProfile, raw_text: str, tailored: TailoredResume) -> VerificationResult:
    c = _Checker(original, raw_text)
    c.check_contact(tailored)
    c.check_skills(tailored)
    c.check_experience(tailored)
    c.check_education(tailored)
    c.check_projects(tailored)
    c.check_free_lists(tailored)
    c.check_summary(tailored)
    if any(i.severity == "error" for i in c.issues):
        status = "rejected"
    elif c.issues:
        status = "flagged"
    else:
        status = "verified"
    return VerificationResult(status=status, issues=c.issues)
