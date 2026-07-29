"""Clientes de APIs externas con Confirmation Gate.

Todos los clientes heredan de BaseExternalClient y operan bajo la allowlist
definida en allowlist.py. Ninguna operación se ejecuta sin confirmación
manual explícita del usuario.
"""
