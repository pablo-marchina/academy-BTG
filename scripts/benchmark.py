"""Benchmark de performance do pipeline."""
import asyncio
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, timedelta


async def benchmark():
    print("=" * 60)
    print("BTG Intelligence - Benchmark de Performance")
    print("=" * 60)

    from src.collectors.pipeline import CollectionPipeline

    tempos = {}

    # Benchmark 1: inicializacao
    t0 = time.time()
    pipeline = CollectionPipeline()
    tempos["init"] = time.time() - t0
    print(f"\n1. Inicializacao: {tempos['init']:.2f}s")

    # Benchmark 2: anbima
    t0 = time.time()
    try:
        async with pipeline.anbima:
            ofertas, docs = await pipeline.anbima.collect()
        tempos["anbima"] = time.time() - t0
        print(f"2. ANBIMA: {tempos['anbima']:.2f}s ({len(ofertas)} ofertas)")
    except Exception as e:
        tempos["anbima"] = time.time() - t0
        print(f"2. ANBIMA: {tempos['anbima']:.2f}s (ERRO: {e})")

    # Benchmark 3: BCB macro
    t0 = time.time()
    try:
        macro = await pipeline.bcb.collect_macro()
        tempos["bcb"] = time.time() - t0
        print(f"3. BCB: {tempos['bcb']:.2f}s (SELIC={macro.get('selic_atual')})")
    except Exception as e:
        tempos["bcb"] = time.time() - t0
        print(f"3. BCB: {tempos['bcb']:.2f}s (ERRO: {e})")

    # Benchmark 4: normalizacao
    from src.analytics.normalizacao import normalizar_oferta
    t0 = time.time()
    for _ in range(1000):
        normalizar_oferta({"produto": "debenture", "indexador": "CDI", "taxa_raw": "1.35", "vencimento": "2030-01-01"})
    tempos["normalizacao_1k"] = time.time() - t0
    print(f"4. Normalizacao (1000x): {tempos['normalizacao_1k']:.3f}s")

    # Benchmark 5: score
    from src.analytics.score import calcular_score
    t0 = time.time()
    for _ in range(1000):
        calcular_score({"produto": "debenture", "codigo": "X", "vencimento": "2030-01-01", "rating": "AA"})
    tempos["score_1k"] = time.time() - t0
    print(f"5. Score (1000x): {tempos['score_1k']:.3f}s")

    # Benchmark 6: clustering
    from src.analytics.clustering import clusterizar_ofertas
    t0 = time.time()
    ofertas = [{"produto": "debenture", "indexador": "CDI", "rating": "AA", "spread_bps": i, "prazo_meses": 24, "volume_mm": 100} for i in range(100)]
    clusterizar_ofertas(ofertas)
    tempos["cluster_100"] = time.time() - t0
    print(f"6. Clustering (100 ofertas): {tempos['cluster_100']:.3f}s")

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    for nome, tempo in tempos.items():
        print(f"  {nome:25s} {tempo:.3f}s")

    total = sum(tempos.values())
    print(f"  {'TOTAL':25s} {total:.3f}s")


if __name__ == "__main__":
    asyncio.run(benchmark())
