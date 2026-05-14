"""
main.py — ponto de entrada do pipeline de inteligência BTG.

Uso:
    python main.py                          # coleta + análise (últimos 30 dias)
    python main.py --dias 7                 # coleta dos últimos 7 dias
    python main.py --sem-pdfs               # coleta sem baixar PDFs
    python main.py --apenas-macro           # coleta só dados macro (BCB)
    python main.py --chat                   # modo conversacional (agente ReAct)
    python main.py --retention              # limpa dados antigos
    python main.py --treinar-ml             # treina modelos ML
"""
import asyncio
import argparse
import logging
import os
import sys
from datetime import date, timedelta

from src.config import settings

settings.setup_dirs()

LOG_JSON = os.environ.get("LOG_JSON", "").lower() in ("1", "true", "yes")

if LOG_JSON:
    from src.api.logging_config import JSONFormatter
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO), handlers=[handler])
else:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(settings.LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

from src.api.logging_config import setup_sentry
setup_sentry()

from src.agents.gestor import run_pipeline
from src.collectors.bcb_collector import BCBCollector


async def main(args: argparse.Namespace) -> None:
    settings.setup_dirs()

    if args.chat:
        from src.agents.reagente import main as chat_main
        chat_main()
        return

    if args.apenas_macro:
        await testar_macro()
        return

    data_inicio = date.today() - timedelta(days=args.dias)

    print(f"\n{'='*60}")
    print(f"  BTG Intelligence - Pipeline de Inteligencia")
    print(f"  Periodo: {data_inicio.isoformat()} -> {date.today().isoformat()}")
    print(f"{'='*60}\n")

    resultado = await run_pipeline(
        data_inicio=data_inicio,
        baixar_pdfs=not args.sem_pdfs,
    )

    analise = resultado.get("analise", {})
    ofertas = resultado.get("ofertas", [])
    macro = resultado.get("macro", {})

    print(f"\n{'-'*60}")
    print(f"  RESULTADO")
    print(f"{'-'*60}")
    print(f"  {analise.get('resumo', 'Sem resumo')}")
    print(f"  Ofertas únicas:  {len(ofertas)}")
    print(f"  SELIC atual:     {macro.get('selic_atual', 0):.2f}%")
    print(f"  IPCA 12m:        {macro.get('ipca_12m', 0):.2f}%")
    print(f"  Regime mercado:  {macro.get('regime_mercado', 'indefinido')}")
    print(f"{'─'*60}\n")

    from collections import Counter
    por_fonte = Counter(o.get("fonte", "?") for o in ofertas)
    por_produto = Counter(o.get("produto", "?") for o in ofertas)

    print("  Por fonte:")
    for fonte, qtd in sorted(por_fonte.items(), key=lambda x: -x[1]):
        print(f"    {fonte:<20} {qtd:>4}")

    print("\n  Por produto:")
    for produto, qtd in sorted(por_produto.items(), key=lambda x: -x[1]):
        print(f"    {produto:<20} {qtd:>4}")

    curva = macro.get("curva_di", {})
    if curva:
        print("\n  Curva DI estimada (meses: taxa %):")
        for prazo, taxa in sorted(curva.items()):
            print(f"    {prazo:>4} meses -> {taxa:.2f}%")

    print()


async def testar_macro() -> None:
    print("\n  Testando coleta macro (BCB)...")
    bcb = BCBCollector()
    data_inicio = date.today() - timedelta(days=365)
    resultado = await bcb.collect_macro(data_inicio=data_inicio)

    print(f"  SELIC atual:         {resultado.get('selic_atual', 0):.2f}%")
    print(f"  SELIC próxima:       {resultado.get('selic_proxima', 0):.2f}%")
    print(f"  IPCA 12m:            {resultado.get('ipca_12m', 0):.2f}%")
    print(f"  IPCA Focus 12m:      {resultado.get('ipca_proximo_12m', 0):.2f}%")
    print(f"  IGPM 12m:            {resultado.get('igpm_12m', 0):.2f}%")
    print(f"  Regime de mercado:   {resultado.get('regime_mercado', 'indefinido')}")

    curva = resultado.get("curva_di", {})
    if curva:
        print("\n  Curva DI estimada:")
        for prazo, taxa in sorted(curva.items()):
            print(f"    {prazo:>4} meses -> {taxa:.2f}%")

    focus_ipca = resultado.get("focus", {}).get("ipca", [])
    if focus_ipca:
        print(f"\n  Focus IPCA (última leitura): {focus_ipca[0]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BTG Intelligence — Pipeline de inteligência")
    parser.add_argument("--dias", type=int, default=30, help="Dias para buscar (default: 30)")
    parser.add_argument("--sem-pdfs", action="store_true", help="Não baixar PDFs")
    parser.add_argument("--apenas-macro", action="store_true", help="Testar só dados macro BCB")
    parser.add_argument("--chat", action="store_true", help="Modo conversacional (agente ReAct)")
    parser.add_argument("--retention", type=int, nargs="?", const=90, help="Limpar dados mais velhos que N dias")
    parser.add_argument("--treinar-ml", action="store_true", help="Treinar modelos ML")
    args = parser.parse_args()

    if args.retention:
        from src.db.retention import limpar_dados_antigos
        limpar_dados_antigos(args.retention)
        sys.exit(0)

    if args.treinar_ml:
        from src.analytics.score_xgb import treinar_xgboost
        from src.analytics.score_ml import treinar_modelo
        from src.analytics.anomalies import treinar_deteccao_anomalias
        print("Treinando XGBoost...", treinar_xgboost())
        print("Treinando Score ML...", treinar_modelo())
        print("Treinando anomalias...", treinar_deteccao_anomalias())
        sys.exit(0)

    asyncio.run(main(args))
