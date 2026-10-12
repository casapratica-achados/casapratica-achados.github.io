"""Libera os pins agendados nos feeds RSS (roda de hora em hora no GitHub Actions).

Lê `agenda.json` (escrita pelo central-core) e monta `feeds/<pasta>.xml` (RSS 2.0) com os itens
cujo `liberar_em` já passou, no máximo os 50 mais recentes, em ordem crescente. Com
`pausado: true` (kill switch), não mexe em nada. Só a biblioteca padrão; só gera XML.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

LIMITE = 50


def _data(texto: str) -> datetime:
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _feed(pasta: str, itens: list[dict], site: str) -> str:
    rss = ET.Element("rss", {"version": "2.0"})
    canal = ET.SubElement(rss, "channel")
    ET.SubElement(canal, "title").text = pasta
    ET.SubElement(canal, "link").text = site
    ET.SubElement(canal, "description").text = f"Achados: {pasta}"
    ET.SubElement(canal, "language").text = "pt-br"
    for it in itens:
        el = ET.SubElement(canal, "item")
        ET.SubElement(el, "title").text = it["titulo"]
        ET.SubElement(el, "description").text = it["descricao"]
        ET.SubElement(el, "link").text = f"{site}/{it['pagina']}"
        ET.SubElement(el, "guid", {"isPermaLink": "false"}).text = it["id"]
        ET.SubElement(el, "pubDate").text = format_datetime(_data(it["liberar_em"]))
        ET.SubElement(el, "enclosure", {"url": f"{site}/{it['imagem']}", "type": "image/png",
                                        "length": str(it["imagem_bytes"])})
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"


def montar_feeds(agenda: dict, agora: datetime) -> dict[str, str]:
    """Pasta → XML do feed, só com itens vencidos (`liberar_em <= agora`)."""
    site = agenda["site"].rstrip("/")
    por_pasta: dict[str, list[dict]] = {}
    for it in agenda["itens"]:
        if _data(it["liberar_em"]) <= agora:
            por_pasta.setdefault(it["pasta"], []).append(it)
    feeds = {}
    for pasta, itens in por_pasta.items():
        itens.sort(key=lambda i: (i["liberar_em"], i["id"]))
        feeds[pasta] = _feed(pasta, itens[-LIMITE:], site)
    return feeds


def main(raiz: Path, agora: datetime | None = None) -> list[str]:
    """Reescreve só os feeds que mudaram; devolve os caminhos alterados."""
    agenda = json.loads((raiz / "agenda.json").read_text(encoding="utf-8"))
    if agenda.get("pausado"):
        return []
    agora = agora or datetime.now(timezone.utc)
    feeds = montar_feeds(agenda, agora)
    pasta_feeds = raiz / "feeds"
    pasta_feeds.mkdir(exist_ok=True)
    alterados = []
    existentes = {p.stem for p in pasta_feeds.glob("*.xml")}
    # pasta que ficou sem itens liberados: feed vazio (o Pinterest continua lendo sem erro)
    for pasta in existentes - set(feeds):
        feeds[pasta] = _feed(pasta, [], agenda["site"].rstrip("/"))
    for pasta, xml in sorted(feeds.items()):
        arq = pasta_feeds / f"{pasta}.xml"
        if not arq.exists() or arq.read_text(encoding="utf-8") != xml:
            arq.write_text(xml, encoding="utf-8", newline="\n")
            alterados.append(f"feeds/{pasta}.xml")
    return alterados


if __name__ == "__main__":
    for caminho in main(Path(".")):
        print("atualizado:", caminho)
