"""
Adaptadores: las implementaciones reales de los puertos de `application`.

Aquí sí hay SQLite, archivos, subprocesos, HTTP y el motor. Este paquete no se
importa desde `domain` ni desde `application`; solo lo conoce la raíz de
composición (`app/container.py`) y el worker de render, que corre aparte.
"""
