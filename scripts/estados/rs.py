"""Rio Grande do Sul — Sistema LEGIS da Assembleia Legislativa (al.rs.gov.br/legis).

Índice: pesquisa por tipo (POST em M0100008.asp, sessão ASP) e resultados paginados em M0100017.asp.
Texto: M0100099.asp traz um iframe com o PDF da norma (filerepository/repLegis), que tem camada de texto.
"""
import html as htmllib
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from comum import (  # noqa: E402
    RAIZ_ESTADUAIS, UA, Rede, caminhos, decodificar, documento_para_md, executar, gravar, html_para_md,
)

UF = "RS"
B = "https://www.al.rs.gov.br/legis/M010/"
# cboTipoNorma do LEGIS -> (pasta, tipo canônico, prefixo). O seletor oferece dez tipos e o
# raspador pedia quatro. Ficam de fora "DIV - DIVERSOS", que é caixa de miscelânea sem espécie
# definida, e "OSG - ORDEM DE SERVIÇO DO GOVERNADOR", que é ato de administração interna.
# Os quatro primeiros prefixos já estão gravados e não mudam.
TIPOS = {
    "23": ("emendas-constitucionais", "Emenda Constitucional", "ec"),
    "2": ("leis-complementares", "Lei Complementar", "lc"),
    "20": ("leis-ordinarias", "Lei Ordinária", "lei"),
    "26": ("decretos-lei", "Decreto-Lei", "dl"),
    "3": ("decretos", "Decreto", "dec"),
    "4": ("decretos-legislativos", "Decreto Legislativo", "dlg"),
    "22": ("resolucoes", "Resolução", "res"),
    "5": ("resolucoes", "Resolução", "res-mesa"),
}
CABECALHO = {"Assembleia Legislativa do Estado do Rio Grande do Sul", "Sistema LEGIS - Texto da Norma",
             "Carregando a página. Aguarde...", "Carregando a página. Aguarde ..."}
rede = Rede(rps=3)
LINHA = re.compile(
    r'name="Hid_NumeroNorma\d+" value="([^"]*)".*?name="Hid_IdNorma\d+" value="(\d+)".*?'
    r'<td[^>]*class="TextoMenor2"[^>]*>\s*([\d/]+)\s*</td>\s*<td[^>]*class="TextoMenor2"[^>]*>(.*?)</td>',
    re.S,
)


class SemRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def sessao():
    cj = http.cookiejar.CookieJar()
    return (
        urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)),
        urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), SemRedirect),
    )


def abrir(op, caminho, dados=None, ref=None, tentativas=5):
    h = {"User-Agent": UA, **({"Referer": ref} if ref else {})}
    req = urllib.request.Request(B + caminho, data=urllib.parse.urlencode(dados).encode() if dados else None, headers=h)
    for n in range(tentativas):
        rede.limite.esperar()
        try:
            return op.open(req, timeout=300).read().decode("latin-1")
        except urllib.error.HTTPError:
            raise  # o 302 da pesquisa é tratado por quem chama
        except Exception:
            if n == tentativas - 1:
                raise
            time.sleep(5 * (n + 1) ** 2)


def indice(refazer=False):
    pasta = os.path.join(RAIZ_ESTADUAIS, UF, "_indice")
    arq = os.path.join(pasta, "legis.json")
    if os.path.exists(arq) and not refazer:
        return json.load(open(arq, encoding="utf-8"))
    itens = []
    for tipo in TIPOS:
        op, op_sr = sessao()
        abrir(op, "M0100008.ASP")
        form = dict(
            Hid_IdNorma="", txthNRO_PROPOSICAO="", txthAdin="", txthQualquerPalavra="", txtTipoPesq="dirigida",
            cboTipoNorma=tipo, TxtNumero_Norma="", TxtAno="", txtData="", txtDataInicial="", txtDataFinal="",
            txtPalavraChave="", TxtQualquerPalavra="", CmbPROPOSICAO="", txtProcAdin="", cmbNumero_Docs="50",
            txtOrdenacao="data", txtOperacaoFormulario="Pesquisar",
        )
        try:
            abrir(op_sr, "M0100008.asp", form, B + "M0100008.ASP")
        except urllib.error.HTTPError as e:
            if e.code != 302:
                raise
        pag = 1
        while True:
            html = abrir(op, f"M0100017.asp?txtPage={pag}&txtNumDocs=50")
            achados = LINHA.findall(html)
            for numero, id_, data, ementa in achados:
                itens.append({
                    "id": id_, "tipo": tipo, "numero": numero, "data": data,
                    "ementa": " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", ementa)).split()),
                })
            total = re.search(r"de\s*(\d+)\s*</", html) or re.search(r"Documentos:.*?de\s*(\d+)", re.sub(r"<[^>]+>", " ", html))
            if not achados or (total and pag * 50 >= int(total.group(1))):
                break
            pag += 1
        print(f"[{UF}] índice tipo {tipo}: {sum(1 for i in itens if i['tipo'] == tipo)}", flush=True)
    os.makedirs(pasta, exist_ok=True)
    with open(arq, "w", encoding="utf-8") as f:
        json.dump(itens, f, ensure_ascii=False)
    return itens


def processar(it):
    pasta, nome, prefixo = TIPOS[it["tipo"]]
    d, m, a = it["data"].split("/") if it["data"].count("/") == 2 else ("", "", "")
    ano = a or "sem-ano"
    slug = f"{prefixo}-{it['numero'] or 'sn'}-{ano}-id{it['id']}"
    md, fonte = caminhos(UF, pasta, ano, slug)
    if os.path.exists(md):
        return "pulado", None
    st, bruto, ctype = rede.get(f"{B}M0100099.asp?Hid_Tipo=TEXTO&Hid_TodasNormas={it['id']}&hTexto=&Hid_IDNorma={it['id']}")
    if st != 200 or not bruto:
        return "sem_texto", {"id": it["id"], "http": st}
    src = re.search(rb"<iframe[^>]*src='([^']+)'", bruto, re.I) or re.search(rb'<iframe[^>]*src="([^"]+)"', bruto, re.I)
    if src:  # normas recentes: PDF num iframe
        url = src.group(1).decode("latin-1").replace(" ", "%20")
        st, doc, ctype = rede.get(url, timeout=300)
        if st != 200 or not doc:
            return "sem_texto", {"id": it["id"], "url": url, "http": st}
    else:  # normas antigas: o texto vem na própria página, em HTML
        url = f"{B}M0100099.asp?Hid_Tipo=TEXTO&Hid_TodasNormas={it['id']}&hTexto=&Hid_IDNorma={it['id']}"
        doc = bruto
    corpo, motivo = documento_para_md(doc, url, ctype, CABECALHO)
    if corpo is None:
        return "sem_texto", {"id": it["id"], "url": url, "motivo": motivo}
    numero_fmt = f"{int(it['numero']):,}".replace(",", ".") if it["numero"].isdigit() else it["numero"]
    titulo = f"{nome} nº {numero_fmt}, de {it['data']}"
    meta = [
        ("titulo", titulo),
        ("uf", UF),
        ("tipo", nome),
        ("numero", it["numero"]),
        ("data", f"{a}-{m}-{d}" if a else ""),
        ("ementa", it["ementa"]),
        ("versao_texto", "PDF da Assembleia Legislativa (pode conter texto compilado)"),
        ("fonte", f"{B}M0100018.asp?Hid_IdNorma={it['id']}&Texto=&Origem=1"),
        ("arquivo", url),
    ]
    gravar(md, fonte, doc, meta, f"# {titulo}\n\n{corpo}")
    return "ok", None


# A Constituição Estadual não está no LEGIS; o texto compilado fica no portal do DAL.
CONST_URL = "https://www2.al.rs.gov.br/dal/LinkClick.aspx?fileticket=WQdIfqNoXO4%3d&tabid=3683&mid=5359"
CONST_PAGINA = ("https://www2.al.rs.gov.br/dal/Legisla%C3%A7%C3%A3o/Constitui%C3%A7%C3%A3o"
                "Estadual/tabid/3683/Default.aspx")


def constituicao():
    md, fonte = caminhos(UF, "constituicao", "1989", "constituicao-rs")
    if os.path.exists(md):
        return
    st, bruto, _ = rede.get(CONST_URL)
    if st != 200 or not bruto:
        print(f"[{UF}] constituição: HTTP {st}", flush=True)
        return
    corpo = html_para_md(decodificar(bruto), {"Constituição Estadual", "Constituição Estadual Compilada"})
    titulo = "Constituição do Estado do Rio Grande do Sul de 1989"
    meta = [
        ("titulo", titulo),
        ("uf", UF),
        ("tipo", "Constituição Estadual"),
        ("data", "1989-10-03"),
        ("versao_texto", "compilada (texto vigente)"),
        ("fonte", CONST_PAGINA),
        ("arquivo", CONST_URL),
    ]
    gravar(md, fonte, bruto, meta, f"# {titulo}\n\n{corpo}")
    print(f"[{UF}] constituição salva", flush=True)


if __name__ == "__main__":
    constituicao()
    itens = indice(refazer="--refazer" in sys.argv)
    itens.sort(key=lambda i: "".join(reversed(i["data"].split("/"))), reverse=True)
    print(f"[{UF}] {len(itens)} normas no índice", flush=True)
    limite = [a for a in sys.argv[1:] if a.isdigit()]
    if limite:
        itens = itens[: int(limite[0])]
    executar(UF, itens, processar, workers=3)
