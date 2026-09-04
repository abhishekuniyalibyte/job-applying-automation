from app.schemas.resume import TailoredResume


def render_markdown(t: TailoredResume) -> str:
    lines: list[str] = []
    if t.full_name:
        lines.append(f"# {t.full_name}")
    contact = " | ".join(x for x in [t.email, t.phone, t.location] if x)
    if contact:
        lines.append(contact)
    if t.summary:
        lines += ["", "## Summary", t.summary]
    if t.skills:
        lines += ["", "## Skills", ", ".join(t.skills)]
    if t.experience:
        lines += ["", "## Experience"]
        for e in t.experience:
            dates = " – ".join(d for d in [e.start_date, e.end_date] if d)
            head = f"**{e.title}**, {e.company}" + (f" ({dates})" if dates else "")
            lines.append(head)
            lines += [f"- {b}" for b in e.bullets]
            lines.append("")
    if t.projects:
        lines += ["## Projects"]
        for p in t.projects:
            tech = f" — {', '.join(p.technologies)}" if p.technologies else ""
            lines.append(f"**{p.name}**{tech}")
            if p.description:
                lines.append(p.description)
            lines += [f"- {b}" for b in p.bullets]
            lines.append("")
    if t.education:
        lines += ["## Education"]
        for ed in t.education:
            dates = " – ".join(d for d in [ed.start_date, ed.end_date] if d)
            deg = ", ".join(x for x in [ed.degree, ed.field_of_study] if x)
            lines.append(f"**{ed.institution}**" + (f" — {deg}" if deg else "") + (f" ({dates})" if dates else ""))
            lines += [f"- {d}" for d in ed.details]
        lines.append("")
    if t.certifications:
        lines += ["## Certifications"] + [f"- {c}" for c in t.certifications] + [""]
    if t.achievements:
        lines += ["## Achievements"] + [f"- {a}" for a in t.achievements] + [""]
    return "\n".join(lines).strip() + "\n"
