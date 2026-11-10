"""
Casos de uso del estudio.

Orquestan el dominio y hablan con el exterior solo a través de los puertos de
`ports.py`. No importan FastAPI, SQLite, requests ni el motor: cualquier
implementación que cumpla el puerto vale, y en las pruebas son dobles en
memoria.
"""
