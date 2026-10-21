"""Gate conservador para suplemento próprio explicitamente referido mas ausente.

Não afirma cobertura de todas as remissões: retém apenas casos em que o decreto
baixa anexo próprio e o HTML termina no fecho e assinaturas, sem suplemento,
tabela ou conteúdo visual validável. Links/rótulos não equivalem ao suplemento.
Referências a outra norma não bastam.
"""
import re
import unicodedata


def normal(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def anexo_proprio_ausente(corpo, parsed):
    if parsed.visual or parsed.structure:
        return None
    # Links are references; only their visible label enters the content test.
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', corpo)
    text = re.sub(r'<a\b[^>]*>(.*?)</a>', r'\1', text, flags=re.I | re.S)
    clean = normal(re.sub(r'[*_`#]', '', text))
    blocks = [re.sub(r'\s+', ' ', b).strip() for b in clean.split('\n\n') if b.strip()]
    fechamento = next((i for i, b in enumerate(blocks)
                        if re.match(r'^(?:brasilia|rio de janeiro)[,.;\s]+(?:em\s*)?\d', b)), None)
    if fechamento is None:
        return None
    principal = '\n'.join(blocks[:fechamento])
    # Explicit deixis identifies this decree; mentions of Decreto nº X alone do not.
    remissao = re.search(r'que com este baixa[m]?|anex[oa]s? a este decreto|anex[oa]s? ao presente decreto', principal)
    if not remissao:
        return None
    apos = blocks[fechamento + 1:]
    heading = re.compile(r'^(?:anexo|regulamento|regimento|tabela|quadro|relacao|convencao|acordo)\b')
    if any(re.match(r'^art\.?\s*\d', b) for b in apos):
        return None
    # A bare annex title/link is not its body; an effective internal target has content.
    for i, b in enumerate(apos):
        if heading.match(b) and any(not heading.match(rest) and not re.search(r'publicad[oa]|disponivel|diario oficial', rest) for rest in apos[i+1:]):
            return None
    # Bounded signing tail, with an optional source note about separate publication.
    notas = [b for b in apos if re.search(r'publicad[oa]|diario oficial', b)]
    assinaturas = [b for b in apos if b not in notas and not heading.match(b)]
    if any(len(b) > 120 or re.search(r'[.;:!?]', b) for b in assinaturas) or len(' '.join(apos)) > 650:
        return None
    return {'motivo': 'Suplemento próprio baixado pelo decreto ausente do HTML: somente fecho, assinaturas, eventual nota de publicação ou rótulo/link; sem o corpo do suplemento.',
            'remissao': principal[max(0, remissao.start()-120):remissao.end()+120], 'fecho': blocks[fechamento], 'apos_fecho': apos}
