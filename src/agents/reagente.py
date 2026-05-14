from __future__ import annotations
import json
import os
import unicodedata
import warnings
from pathlib import Path
from typing import Optional

import pandas as pd
from langchain_core.tools import tool
from langchain_groq import ChatGroq

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langgraph.prebuilt import create_react_agent

from ..config import settings


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "cvm"

_df_cvm: Optional[pd.DataFrame] = None
_carteira_xp: Optional[dict] = None
_meelion: Optional[list] = None


def _carregar_dados():
    global _df_cvm, _carteira_xp, _meelion
    if _df_cvm is not None:
        return

    csv_path = DATA_DIR / "oferta_resolucao_160.csv"
    if csv_path.exists():
        _df_cvm = pd.read_csv(csv_path, sep=";")
        _df_cvm["Data_Registro"] = pd.to_datetime(_df_cvm["Data_Registro"], errors="coerce")
        _df_cvm["Ano"] = _df_cvm["Data_Registro"].dt.year

    json_xp = DATA_DIR / "carteira_xp_maio2026.json"
    if json_xp.exists():
        with open(json_xp, encoding="utf-8") as f:
            _carteira_xp = json.load(f)

    json_meelion = Path(__file__).resolve().parents[2] / "data" / "meelion" / "investimentos_page1.json"
    if json_meelion.exists():
        with open(json_meelion, encoding="utf-8") as f:
            _meelion = json.load(f)


@tool
def resumo_mercado_cvm() -> str:
    """Retorna um resumo geral do mercado de ofertas primárias registradas na CVM
    (2023–2026): total de ofertas, volume financeiro, breakdown por tipo de ativo
    e pelos maiores líderes de distribuição."""
    _carregar_dados()
    if _df_cvm is None or _df_cvm.empty:
        return "Dados CVM não disponíveis."
    total = len(_df_cvm)
    volume = _df_cvm["Valor_Total_Registrado"].sum() / 1e9
    por_tipo = (
        _df_cvm.groupby("Valor_Mobiliario")["Valor_Total_Registrado"]
        .agg(qtd="count", volume_bi=lambda x: x.sum() / 1e9)
        .sort_values("volume_bi", ascending=False)
        .head(8)
    )
    por_lider = (
        _df_cvm.groupby("Nome_Lider")["Valor_Total_Registrado"]
        .agg(qtd="count", volume_bi=lambda x: x.sum() / 1e9)
        .sort_values("volume_bi", ascending=False)
        .head(6)
    )
    por_ano = (
        _df_cvm.groupby("Ano")["Valor_Total_Registrado"]
        .agg(qtd="count", volume_bi=lambda x: x.sum() / 1e9)
        .sort_index()
    )
    return (
        f"RESUMO MERCADO CVM (Resolução 160 — 2023 a 2026)\n"
        f"Total de ofertas registradas: {total:,}\n"
        f"Volume total: R$ {volume:.1f} bilhões\n\n"
        f"Por tipo de ativo (top 8):\n{por_tipo.to_string()}\n\n"
        f"Por líder de distribuição (top 6):\n{por_lider.to_string()}\n\n"
        f"Por ano:\n{por_ano.to_string()}"
    )


@tool
def buscar_ofertas_cvm(tipo: str = "", lider: str = "", ano: int = 0, limite: int = 10) -> str:
    """Busca ofertas primárias na base da CVM com filtros opcionais.
    Parâmetros: tipo (Debêntures, CRI, CRA, FIDC, FII), lider (BTG, XP, Itaú), ano, limite."""
    _carregar_dados()
    if _df_cvm is None or _df_cvm.empty:
        return "Dados CVM não disponíveis."
    df = _df_cvm.copy()

    def normalize(s: str) -> str:
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()

    if tipo:
        df = df[df["Valor_Mobiliario"].map(normalize).str.contains(normalize(tipo), case=False, na=False)]
    if lider:
        df = df[df["Nome_Lider"].map(normalize).str.contains(normalize(lider), case=False, na=False)]
    if ano:
        df = df[df["Ano"] == ano]

    if df.empty:
        return "Nenhuma oferta encontrada com os filtros informados."

    cols = ["Data_Registro", "Valor_Mobiliario", "Nome_Emissor", "Nome_Lider",
            "Valor_Total_Registrado", "Status_Requerimento"]
    resultado = df[cols].sort_values("Data_Registro", ascending=False).head(limite)
    resultado = resultado.copy()
    resultado["Valor_Total_Registrado"] = resultado["Valor_Total_Registrado"].apply(
        lambda v: f"R$ {v/1e6:.1f}M" if pd.notna(v) else "N/D"
    )
    resultado["Data_Registro"] = resultado["Data_Registro"].dt.strftime("%d/%m/%Y")

    return (
        f"Encontradas {len(df):,} ofertas (exibindo {min(limite, len(df))}):\n\n"
        + resultado.to_string(index=False)
    )


@tool
def carteira_recomendada_xp() -> str:
    """Retorna a carteira de renda fixa recomendada pela XP Investimentos para Maio 2026."""
    _carregar_dados()
    if _carteira_xp is None:
        return "Dados da carteira XP não disponíveis."
    c = _carteira_xp
    linhas = [
        f"CARTEIRA XP — {c['data_referencia']}",
        f"Instituição: {c['instituicao']}",
        f"Estratégia: {c['resumo_estrategia']}",
        f"Fonte: {c['fonte_url']}",
        f"\n{len(c['titulos'])} títulos recomendados:",
    ]
    for i, t in enumerate(c["titulos"], 1):
        ir = " [ISENTO IR]" if t["isento_ir"] else ""
        gross = f" | Gross-up: {t['taxa_gross_up']}" if t.get("taxa_gross_up") else ""
        linhas.append(
            f"\n  {i}. {t['ativo_emissor']}{ir}\n"
            f"     Indexador: {t['indexador']} | Taxa: {t['taxa_bruta']}{gross}\n"
            f"     Vencimento: {t['vencimento']}"
        )
    return "\n".join(linhas)


@tool
def investimentos_meelion() -> str:
    """Retorna investimentos de renda fixa disponíveis no comparador Meelion (plano free, página 1)."""
    _carregar_dados()
    if _meelion is None:
        return "Dados Meelion não disponíveis."
    linhas = [f"INVESTIMENTOS MEELION ({len(_meelion)} resultados — plano free):"]
    for i, inv in enumerate(_meelion, 1):
        fgc = "Com FGC" if inv["com_fgc"] else "Sem FGC"
        linhas.append(
            f"\n  {i}. {inv['nome']}\n"
            f"     Tipo: {inv['tipo']} | {fgc}\n"
            f"     Emissor: {inv['emissor']} | Distribuidor: {inv['distribuidor']}\n"
            f"     Vencimento: {inv['vencimento']}"
        )
    return "\n".join(linhas)


def build_agent():
    if not settings.GROQ_API_KEY:
        os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
    if not os.environ.get("GROQ_API_KEY"):
        raise EnvironmentError("Defina GROQ_API_KEY no arquivo .env")

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

    tools = [
        resumo_mercado_cvm,
        buscar_ofertas_cvm,
        carteira_recomendada_xp,
        investimentos_meelion,
    ]

    system_prompt = """Você é um analista de mercado financeiro especializado em ofertas primárias de renda fixa no Brasil.

Você tem acesso a dados reais:
- Base CVM (Resolução 160): 13.015 ofertas registradas de 2023 a 2026
- Carteira recomendada da XP Investimentos para Maio 2026
- Investimentos disponíveis no comparador Meelion (scraping ao vivo)

Ao responder:
- Sempre consulte as ferramentas disponíveis antes de responder sobre dados concretos
- Cite volumes em reais (ex: R$ 2,3 bilhões) e use linguagem técnica mas acessível
- Quando relevante, compare fontes diferentes (ex: o que a CVM registrou vs o que a XP recomenda)
- Seja objetivo: números primeiro, interpretação depois
- Se o usuário pedir algo que seus dados não cobrem, diga claramente o que está fora do escopo"""

    return create_react_agent(llm, tools, prompt=system_prompt)


def main():
    print("=" * 60)
    print("  BTG Intelligence — Agente de Análise de Ofertas Primárias")
    print("  Dados: CVM 2023-2026 | Carteira XP | Meelion")
    print("  Digite 'sair' para encerrar")
    print("=" * 60)

    agent = build_agent()

    while True:
        pergunta = input("\nVocê: ").strip()
        if not pergunta or pergunta.lower() in {"sair", "exit", "quit"}:
            print("Encerrando agente.")
            break

        for step in agent.stream(
            {"messages": [{"role": "user", "content": pergunta}]},
            stream_mode="updates",
        ):
            if "tools" in step:
                for msg in step["tools"]["messages"]:
                    print(f"\n  [tool: {msg.name}] → {msg.content[:120]}...")

            if "agent" in step:
                last = step["agent"]["messages"][-1]
                if last.content:
                    print(f"\nAgente: {last.content}")


if __name__ == "__main__":
    main()
