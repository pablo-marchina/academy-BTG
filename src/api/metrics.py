from __future__ import annotations
import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

oferta_coletadas = Counter("btg_ofertas_coletadas_total", "Total de ofertas coletadas", ["fonte"])
pipeline_duration = Histogram("btg_pipeline_duration_seconds", "Duracao do pipeline", buckets=[10, 30, 60, 120, 300, 600, 1800])
pipeline_errors = Counter("btg_pipeline_errors_total", "Erros no pipeline", ["node"])
score_distribution = Gauge("btg_score_atual", "Score atual das ofertas", ["produto"])
ultima_coleta = Gauge("btg_ultima_coleta_timestamp", "Timestamp da ultima coleta")


def export_metrics():
    return generate_latest(REGISTRY)


def registrar_coleta(fonte: str):
    oferta_coletadas.labels(fonte=fonte).inc()


def registrar_erro(node: str):
    pipeline_errors.labels(node=node).inc()


def registrar_duracao(segundos: float):
    pipeline_duration.observe(segundos)


def registrar_ultima_coleta():
    ultima_coleta.set(time.time())
