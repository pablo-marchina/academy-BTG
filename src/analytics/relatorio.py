from __future__ import annotations
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from fpdf import FPDF

from ..db.engine import SessionLocal
from ..db.models import Oferta, ScoreLog

logger = logging.getLogger(__name__)

COR_PRIMARIA = (0, 51, 102)
COR_DESTAQUE = (200, 150, 0)


class ResearchPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*COR_PRIMARIA)
        self.cell(0, 6, "BTG Intelligence - Research de Ofertas Primarias", align="L")
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}} | Confidencial", align="C")

    def titulo(self, texto: str):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*COR_PRIMARIA)
        self.cell(0, 10, texto, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*COR_DESTAQUE)
        self.line(10, self.get_y(), 287, self.get_y())
        self.ln(4)

    def subtitulo(self, texto: str):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*COR_PRIMARIA)
        self.cell(0, 7, texto, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def celula(self, label: str, valor: str):
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(80, 80, 80)
        self.cell(35, 5, label, align="R")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(0, 0, 0)
        self.cell(0, 5, valor, new_x="LMARGIN", new_y="NEXT")

    def tabela(self, cabecalhos: List[str], dados: List[List[str]], col_larguras: List[int]):
        self.set_font("Helvetica", "B", 7)
        self.set_fill_color(*COR_PRIMARIA)
        self.set_text_color(255, 255, 255)
        for h, w in zip(cabecalhos, col_larguras):
            self.cell(w, 6, h, border=1, fill=True)
        self.ln()

        self.set_font("Helvetica", "", 6.5)
        self.set_text_color(0, 0, 0)
        for linha in dados:
            for v, w in zip(linha, col_larguras):
                self.cell(w, 5, str(v)[:w // 2], border=1)
            self.ln()


def gerar_relatorio_research(
    ofertas: Optional[List[Dict[str, Any]]] = None,
    caminho: str = "",
    macro: Optional[Dict[str, Any]] = None,
) -> str:
    if not caminho:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = f"data/relatorio_research_{ts}.pdf"

    pdf = ResearchPDF(orientation="L", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.titulo("Relatorio de Pesquisa - Ofertas Primarias")
    pdf.celula("Data", datetime.now().strftime("%d/%m/%Y %H:%M"))
    if macro:
        pdf.celula("SELIC", f"{macro.get('selic_atual', '-')}%")
        pdf.celula("IPCA 12m", f"{macro.get('ipca_12m', '-')}%")
        pdf.celula("Regime", macro.get("regime_mercado", "-"))
    pdf.ln(6)

    if ofertas:
        pdf.subtitulo(f"Ofertas Analisadas: {len(ofertas)}")

        cabecalhos = ["Emissor", "Produto", "Idx", "Taxa", "Rating", "Score", "Spread", "Coordenador"]
        col_w = [55, 25, 20, 22, 22, 18, 20, 35]
        dados = []
        for o in ofertas[:40]:
            dados.append([
                str(o.get("emissor", ""))[:20],
                str(o.get("produto", "")).upper(),
                str(o.get("indexador", "")),
                str(o.get("taxa_raw", "")),
                str(o.get("rating", "")),
                str(o.get("score", "")),
                str(o.get("spread_bps", "")),
                str(o.get("coordenador", ""))[:15],
            ])

        pdf.tabela(cabecalhos, dados, col_w)

    pdf.output(caminho)
    logger.info(f"[PDF] Relatorio salvo: {caminho}")
    return caminho


def gerar_relatorio_carteira(
    matches: List[Dict[str, Any]],
    perfil_nome: str,
    caminho: str = "",
) -> str:
    if not caminho:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = f"data/carteira_{perfil_nome}_{ts}.pdf"

    pdf = ResearchPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.titulo(f"Carteira Recomendada - Perfil {perfil_nome}")

    for item in matches:
        m = item.get("match", {})
        o = item.get("oferta", {})

        if pdf.get_y() > 240:
            pdf.add_page()

        pdf.subtitulo(f"{o.get('emissor', '?')} - {o.get('produto', '?').upper()}")
        pdf.celula("Taxa", f"{o.get('taxa_raw', '?')} ({o.get('indexador', '?')})")
        pdf.celula("Match", f"{m.get('match_score', 0):.0f}% - {m.get('match_label', '?')}")
        pdf.celula("Vencimento", str(o.get("vencimento", "?")))
        pdf.celula("Coordenador", str(o.get("coordenador", "?")))
        pdf.celula("Rating", str(o.get("rating", "N/D")))

        if m.get("avisos"):
            pdf.set_text_color(180, 100, 0)
            for a in m["avisos"]:
                pdf.cell(0, 4, f"  Obs: {a}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    pdf.output(caminho)
    return caminho
