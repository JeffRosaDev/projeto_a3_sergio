"""Camada de auditoria e persistência append-only em SQLite."""

from .audit_logger import AuditLogger

__all__ = ["AuditLogger"]
