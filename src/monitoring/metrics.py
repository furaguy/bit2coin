# File: src/monitoring/metrics.py

import time
import psutil
import logging
from typing import Dict, List
from dataclasses import dataclass
from prometheus_client import Counter, Gauge, Histogram, start_http_server

@dataclass
class NetworkMetrics:
    connected_peers: int
    blacklisted_peers: int
    messages_processed: int
    network_health: float
    bandwidth_usage: float

@dataclass
class ConsensusMetrics:
    blocks_processed: int
    transactions_processed: int
    validation_time: float
    active_validators: int
    total_stake: float

class MetricsCollector:
    def __init__(self, port: int = 9090):
        # Network metrics
        self.connected_peers = Gauge('connected_peers', 'Number of connected peers')
        self.blacklisted_peers = Gauge('blacklisted_peers', 'Number of blacklisted peers')
        self.message_counter = Counter('messages_processed', 'Total messages processed')
        self.network_health = Gauge('network_health', 'Network health score')
        self.bandwidth_usage = Gauge('bandwidth_usage', 'Current bandwidth usage')

        # Consensus metrics
        self.blocks_processed = Counter('blocks_processed', 'Total blocks processed')
        self.transactions_processed = Counter('transactions_processed', 'Total transactions processed')
        self.validation_time = Histogram('validation_time', 'Block validation time')
        self.active_validators = Gauge('active_validators', 'Number of active validators')
        self.total_stake = Gauge('total_stake', 'Total stake in the network')

        # System metrics
        self.cpu_usage = Gauge('cpu_usage', 'CPU usage percentage')
        self.memory_usage = Gauge('memory_usage', 'Memory usage percentage')
        self.disk_usage = Gauge('disk_usage', 'Disk usage percentage')

        # Start metrics server
        start_http_server(port)

    def update_network_metrics(self, metrics: NetworkMetrics):
        self.connected_peers.set(metrics.connected_peers)
        self.blacklisted_peers.set(metrics.blacklisted_peers)
        self.message_counter.inc(metrics.messages_processed)
        self.network_health.set(metrics.network_health)
        self.bandwidth_usage.set(metrics.bandwidth_usage)

    def update_consensus_metrics(self, metrics: ConsensusMetrics):
        self.blocks_processed.inc()
        self.transactions_processed.inc(metrics.transactions_processed)
        self.validation_time.observe(metrics.validation_time)
        self.active_validators.set(metrics.active_validators)
        self.total_stake.set(metrics.total_stake)

    def update_system_metrics(self):
        self.cpu_usage.set(psutil.cpu_percent())
        self.memory_usage.set(psutil.virtual_memory().percent)
        self.disk_usage.set(psutil.disk_usage('/').percent)