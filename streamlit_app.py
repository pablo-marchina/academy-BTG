from __future__ import annotations
import asyncio
import os
import json
import hashlib
import secrets
from datetime import date, timedelta
from typing import List, Dict, Any
from pathlib import Path

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.config import settings
from src.db.engine import SessionLocal, init_db
from src.db.models import Oferta, MacroDiaria

st.set_page_config(
    page_title="BTG Intelligence",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

_USERS_FILE = Path("data/users.json")
_USERS_FILE.parent.mkdir(exist_ok=True)

USERS: Dict[str, str] = {}


def _hash(senha: str) -> str:
    salt = "btgintel2026"
    return hashlib.sha256((senha + salt).encode()).hexdigest()


def _comparar_senhas(digitada: str, armazenada: str) -> bool:
    if armazenada.startswith("sha256:"):
        expected = "sha256:" + _hash(digitada)
        return hashlib.sha256(expected.encode()).hexdigest() == hashlib.sha256(armazenada.encode()).hexdigest()
    return armazenada == digitada


def _carregar_usuarios():
    global USERS
    if _USERS_FILE.exists():
        try:
            raw = json.loads(_USERS_FILE.read_text())
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if not v.startswith("sha256:"):
                        raw[k] = "sha256:" + _hash(v)
                    else:
                        raw[k] = v
                USERS = raw
        except Exception:
            pass

    if "admin" not in USERS:
        default_pwd = secrets.token_hex(8)
        USERS["admin"] = "sha256:" + _hash(default_pwd)
        _salvar_usuarios()
        print(f"[Auth] Usuario admin criado com senha: {default_pwd}")


def _salvar_usuarios():
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(json.dumps(USERS, indent=2))


_carregar_usuarios()


_verificar_senha = _comparar_senhas


def check_auth():
    if "user" in st.session_state:
        return True
    if "authenticated" in st.session_state:
        return True

    with st.container():
        st.title("BTG Intelligence - Login")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            user = st.text_input("Usuario")
            pwd = st.text_input("Senha", type="password")
            if st.button("Entrar", use_container_width=True):
                if user in USERS and _verificar_senha(pwd, USERS[user]):
                    st.session_state.user = user
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Usuario ou senha incorretos")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Criar conta"):
                    st.session_state.show_signup = True
            with col_b:
                if st.button("Esqueci senha"):
                    st.info("Contate o administrador")
            if st.session_state.get("show_signup"):
                novo_user = st.text_input("Novo usuario")
                nova_pwd = st.text_input("Nova senha", type="password")
                conf_pwd = st.text_input("Confirmar senha", type="password")
                if st.button("Cadastrar"):
                    if not novo_user or not nova_pwd:
                        st.error("Preencha todos os campos")
                    elif nova_pwd != conf_pwd:
                        st.error("Senhas nao conferem")
                    elif novo_user in USERS:
                        st.error("Usuario ja existe")
                    else:
                        USERS[novo_user] = "sha256:" + _hash(nova_pwd)
                        _salvar_usuarios()
                        st.success("Conta criada! Faca login.")
                        st.session_state.show_signup = False
                        st.rerun()
        return False
    return False


if not check_auth():
    st.stop()

st.sidebar.write(f"Usuario: {st.session_state.get('user', 'anonimo')}")
if st.sidebar.button("Sair"):
    st.session_state.clear()
    st.rerun()

st.title("BTG Intelligence - Mercado Primario")
st.markdown("---")


@st.cache_data(ttl=300)
def carregar_ofertas(limite: int = 500) -> pd.DataFrame:
    init_db()
    session = SessionLocal()
    try:
        rows = session.query(Oferta).order_by(Oferta.score_atratividade.desc().nullslast()).limit(limite).all()
        data = []
        for r in rows:
            data.append({
                "id": r.id,
                "codigo": r.codigo,
                "fonte": r.fonte,
                "produto": r.produto,
                "emissor": r.emissor,
                "indexador": r.indexador,
                "taxa_raw": r.taxa_raw,
                "vencimento": r.vencimento,
                "rating": r.rating,
                "coordenador": r.coordenador,
                "volume_mm": r.volume_mm,
                "score": r.score_atratividade,
                "score_confianca": r.score_confianca,
                "spread_bps": r.spread_curva_bps,
                "taxa_cdi": r.taxa_cdi,
                "taxa_ipca": r.taxa_ipca,
                "cluster": r.cluster_peers,
            })
        return pd.DataFrame(data)
    finally:
        session.close()


@st.cache_data(ttl=300)
def carregar_macro() -> Dict[str, Any]:
    init_db()
    session = SessionLocal()
    try:
        row = session.query(MacroDiaria).order_by(MacroDiaria.data.desc()).first()
        if row:
            return {
                "data": row.data.isoformat() if row.data else "",
                "selic_atual": row.selic_atual,
                "selic_proxima": row.selic_proxima,
                "ipca_12m": row.ipca_12m,
                "ipca_proximo_12m": row.ipca_proximo_12m,
                "igpm_12m": row.igpm_12m,
                "regime_mercado": row.regime_mercado,
            }
        return {}
    finally:
        session.close()


df = carregar_ofertas()
macro = carregar_macro()


with st.sidebar:
    st.header("Filtros")
    produtos = ["Todos"] + sorted(df["produto"].dropna().unique().tolist()) if not df.empty else ["Todos"]
    produto_sel = st.selectbox("Produto", produtos)

    indexadores = ["Todos"] + sorted(df["indexador"].dropna().unique().tolist()) if not df.empty else ["Todos"]
    indexador_sel = st.selectbox("Indexador", indexadores)

    score_min = st.slider("Score mínimo", 0, 100, 0)

    if st.button("🔄 Nova Coleta", use_container_width=True):
        with st.spinner("Executando pipeline..."):
            from src.agents.gestor import run_pipeline
            asyncio.run(run_pipeline())
            st.cache_data.clear()
            st.rerun()

    st.metric("SELIC", f"{macro.get('selic_atual', '-'):.2f}%" if macro.get('selic_atual') else "-")
    st.metric("IPCA 12m", f"{macro.get('ipca_12m', '-'):.2f}%" if macro.get('ipca_12m') else "-")
    if macro.get("regime_mercado"):
        st.caption(f"Regime: {macro['regime_mercado']}")


if df.empty:
    st.info("Nenhuma oferta no banco. Execute uma coleta primeiro.")
    st.stop()

df_filtrado = df.copy()
if produto_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["produto"] == produto_sel]
if indexador_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["indexador"] == indexador_sel]
if score_min > 0:
    df_filtrado = df_filtrado[df_filtrado["score"] >= score_min]


tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Ofertas", "🎯 Scoreboard", "📈 Curva vs Ofertas", "🔬 Comparação", "💬 Chat"])


with tab1:
    st.subheader(f"Ofertas ({len(df_filtrado)})")
    cols = ["emissor", "produto", "indexador", "taxa_raw", "rating", "score", "spread_bps", "coordenador", "fonte"]
    df_display = df_filtrado[cols].copy()
    df_display.columns = ["Emissor", "Produto", "Indexador", "Taxa", "Rating", "Score", "Spread(bps)", "Coordenador", "Fonte"]

    for c in ["Score", "Spread(bps)"]:
        if c in df_display.columns:
            df_display[c] = df_display[c].round(1)

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn(format="%.1f"),
            "Spread(bps)": st.column_config.NumberColumn(format="%.0f"),
        },
    )


with tab2:
    st.subheader("Scoreboard")

    col_a, col_b = st.columns(2)

    with col_a:
        if not df_filtrado.empty and "score" in df_filtrado.columns:
            fig_hist = px.histogram(
                df_filtrado.dropna(subset=["score"]),
                x="score",
                nbins=20,
                title="Distribuição de Scores",
                labels={"score": "Score"},
                color_discrete_sequence=["#1f77b4"],
            )
            fig_hist.update_layout(height=350)
            st.plotly_chart(fig_hist, use_container_width=True)

    with col_b:
        if not df_filtrado.empty and "produto" in df_filtrado.columns:
            score_produto = df_filtrado.groupby("produto")["score"].mean().reset_index()
            fig_bar = px.bar(
                score_produto,
                x="produto", y="score",
                title="Score Médio por Produto",
                labels={"produto": "Produto", "score": "Score Médio"},
                color="score",
                color_continuous_scale="blues",
            )
            fig_bar.update_layout(height=350)
            st.plotly_chart(fig_bar, use_container_width=True)

    if not df_filtrado.empty:
        st.subheader("Top 10 Ofertas")
        top10 = df_filtrado.dropna(subset=["score"]).nlargest(10, "score")[
            ["emissor", "produto", "indexador", "taxa_raw", "score", "rating", "coordenador"]
        ]
        top10.columns = ["Emissor", "Produto", "Indexador", "Taxa", "Score", "Rating", "Coordenador"]
        st.dataframe(top10, use_container_width=True, hide_index=True)


with tab3:
    st.subheader("Curva DI vs Ofertas")

    if macro.get("curva_di"):
        curva = macro["curva_di"]
        df_curva = pd.DataFrame([
            {"prazo_meses": int(k), "taxa": float(v)}
            for k, v in curva.items()
        ]).sort_values("prazo_meses")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_curva["prazo_meses"], y=df_curva["taxa"],
            mode="lines+markers", name="Curva DI",
            line=dict(color="red", width=2),
        ))

        if not df_filtrado.empty:
            ofertas_plot = df_filtrado.dropna(subset=["taxa_cdi", "score"])
            fig.add_trace(go.Scatter(
                x=ofertas_plot.get("prazo_meses", [12]*len(ofertas_plot)),
                y=ofertas_plot["taxa_cdi"],
                mode="markers",
                name="Ofertas CDI+",
                marker=dict(
                    size=ofertas_plot["score"].fillna(50) / 5 + 5,
                    color=ofertas_plot["score"].fillna(50),
                    colorscale="Viridis",
                    showscale=True,
                    colorbar_title="Score",
                ),
                text=ofertas_plot["emissor"],
                hovertemplate="<b>%{text}</b><br>Taxa: %{y:.2f}%<br>Score: %{marker.color:.0f}<extra></extra>",
            ))

        fig.update_layout(
            height=450,
            xaxis_title="Prazo (meses)",
            yaxis_title="Taxa (%)",
            hovermode="closest",
        )
        st.plotly_chart(fig, use_container_width=True)

    df_spread = df_filtrado.dropna(subset=["spread_bps", "rating"])
    if not df_spread.empty:
        st.subheader("Spread vs Rating")
        fig_spread = px.box(
            df_spread,
            x="rating", y="spread_bps",
            title="Spread (bps) por Rating",
            color="rating",
            points="all",
        )
        fig_spread.update_layout(height=400)
        st.plotly_chart(fig_spread, use_container_width=True)


with tab4:
    st.subheader("Comparação de Ofertas")

    if not df_filtrado.empty:
        names = df_filtrado["emissor"].dropna().unique().tolist()
        sel = st.multiselect("Selecionar ofertas para comparar", names, default=names[:3] if len(names) >= 3 else names)

        if sel:
            df_comp = df_filtrado[df_filtrado["emissor"].isin(sel)]
            cols_comp = ["emissor", "produto", "indexador", "taxa_raw", "rating", "score", "spread_bps", "coordenador"]
            st.dataframe(
                df_comp[cols_comp],
                use_container_width=True,
                hide_index=True,
            )

            if len(df_comp) >= 2:
                fig_radar = go.Figure()
                for _, row in df_comp.iterrows():
                    score = row.get("score", 0) or 0
                    spread = min(row.get("spread_bps", 0) or 0, 200) / 2
                    rating_num = 50
                    r = str(row.get("rating", ""))
                    if "AAA" in r: rating_num = 100
                    elif "AA" in r: rating_num = 85
                    elif "A" in r: rating_num = 70
                    elif "BBB" in r: rating_num = 55
                    elif "BB" in r: rating_num = 40

                    fig_radar.add_trace(go.Scatterpolar(
                        r=[score, spread, rating_num, 50, 50],
                        theta=["Score", "Spread (adj)", "Rating", "Prazo", "Volume"],
                        fill="toself",
                        name=row.get("emissor", "?"),
                    ))
                fig_radar.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                    height=400,
                )
                st.plotly_chart(fig_radar, use_container_width=True)

with tab5:
    st.subheader("Assistente de Mercado")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Pergunte sobre o mercado (ex: 'quais as melhores ofertas hoje?')"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                from src.agents.reagente import build_agent
                from src.vectorstore.graphrag import get_graphrag

                q = prompt.lower()
                resposta = ""
                place = st.empty()

                if any(p in q for p in ["emissor", "coordenador", "rating", "mercado", "debenture", "cri", "cra", "cdb"]):
                    g = get_graphrag()
                    resposta = g.graph_query(prompt)
                    place.markdown(resposta)

                if not resposta:
                    agent = build_agent()
                    resposta = ""
                    for step in agent.stream(
                        {"messages": [{"role": "user", "content": prompt}]},
                        stream_mode="updates",
                    ):
                        if "agent" in step:
                            last = step["agent"]["messages"][-1]
                            if last.content:
                                resposta += last.content
                                place.markdown(resposta + "▌")

                if not resposta:
                    resposta = "Nao consegui encontrar informacoes para sua pergunta."

                place.markdown(resposta)
                st.session_state.messages.append({"role": "assistant", "content": resposta})
            except Exception as e:
                st.error(f"Erro: {e}")
                st.session_state.messages.append({"role": "assistant", "content": f"Erro ao processar: {e}"})

st.markdown("---")
st.caption("BTG Intelligence v0.1.0 — Pipeline LangGraph | Dados ANBIMA, CVM, BCB, Plataformas")
