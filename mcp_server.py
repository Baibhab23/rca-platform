"""Simple MCP server for the RCA platform with 2 tools."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rca-platform")


@mcp.tool()
def get_platform_status() -> dict:
    """Get the current status of all RCA platform services."""
    return {
        "services": {
            "gateway": "running",
            "ingestion": "running",
            "anomaly_detector": "running",
            "rca_engine": "running",
            "prescriptive": "running",
            "narrative": "running",
        },
        "infrastructure": {
            "redis": "connected",
            "postgres": "connected",
            "kafka": "connected",
        },
        "uptime_seconds": 3600,
    }


@mcp.tool()
def query_anomalies(service: str = "all", limit: int = 10) -> list[dict]:
    """Query recent anomalies detected by the platform.

    Args:
        service: Filter by service name, or "all" for every service.
        limit: Maximum number of anomalies to return (1-100).
    """
    limit = max(1, min(limit, 100))

    sample_anomalies = [
        {"id": "a1", "service": "gateway", "metric": "latency_p99", "value": 850.0, "threshold": 500.0, "severity": "high"},
        {"id": "a2", "service": "ingestion", "metric": "kafka_lag", "value": 12000.0, "threshold": 5000.0, "severity": "medium"},
        {"id": "a3", "service": "anomaly_detector", "metric": "cpu_usage", "value": 92.0, "threshold": 80.0, "severity": "medium"},
        {"id": "a4", "service": "rca_engine", "metric": "memory_mb", "value": 3800.0, "threshold": 3000.0, "severity": "low"},
        {"id": "a5", "service": "gateway", "metric": "error_rate", "value": 0.08, "threshold": 0.05, "severity": "high"},
    ]

    if service != "all":
        sample_anomalies = [a for a in sample_anomalies if a["service"] == service]

    return sample_anomalies[:limit]


if __name__ == "__main__":
    mcp.run()
