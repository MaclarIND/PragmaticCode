"""Carga las claves desde el archivo .env de la carpeta del proyecto (si existe).

Formato, una por línea:  NOMBRE=valor
Las variables que ya estén definidas en el sistema tienen prioridad. El .env nunca se sube al repo (.gitignore).
"""
import os

_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def cargar():
    if not os.path.exists(_ENV):
        return
    with open(_ENV, encoding="utf-8-sig") as f:  # utf-8-sig: el Bloc de notas a veces agrega BOM
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            nombre, valor = linea.split("=", 1)
            valor = valor.strip().strip("\"'")
            if valor:
                os.environ.setdefault(nombre.strip(), valor)


cargar()
