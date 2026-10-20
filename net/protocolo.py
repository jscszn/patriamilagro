"""Protocolo de red: mensajes JSON sobre TCP con prefijo de longitud.

TCP es un flujo de bytes sin fronteras: lo que un lado envía en un `send` puede llegar partido
o pegado al siguiente. Por eso cada mensaje viaja así:

    [4 bytes: longitud N, entero sin signo big-endian][N bytes: JSON en UTF-8]

Mensajes (campo "t" = tipo):
  cliente -> servidor
    hola       {nombre}                 se presenta al conectarse
    rol        {rol}                    pide un rol en la sala
    listo      {listo}                  marca que está listo (sala, informe, resultado)
    ruta       {clave}                  el anfitrión elige la ruta en el informe
    empezar    {}                       el anfitrión arranca la partida
    acciones   {m, p}                   botones mantenidos y recién pulsados (cada frame)
    voto       {decision}               su voto sobre el jefe
    sala       {}                       el anfitrión vuelve a la sala tras el final
  servidor -> cliente
    bienvenida {id}                     el id de jugador que le tocó
    rechazo    {motivo}                 sala llena o partida en curso
    estado     {fase, jugadores, ...}   instantánea del juego (ver net/sesion.py)
"""
from __future__ import annotations

import json
import socket
import struct
from typing import List

PUERTO = 50505
CABECERA = struct.Struct(">I")
MAXIMO = 4 * 1024 * 1024          # un mensaje más grande que esto es un error (o un intruso)


def empaquetar(mensaje: dict) -> bytes:
    datos = json.dumps(mensaje, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return CABECERA.pack(len(datos)) + datos


class Canal:
    """Un socket TCP no bloqueante que envía y recibe mensajes completos."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.sock.setblocking(False)
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # sin retardo de Nagle
        except OSError:
            pass
        self._entrada = bytearray()
        self._salida = bytearray()
        self.abierto = True

    def enviar(self, mensaje: dict) -> None:
        """Encola el mensaje y manda lo que el sistema acepte ahora (el resto, en vaciar())."""
        if self.abierto:
            self._salida += empaquetar(mensaje)
            self.vaciar()

    def vaciar(self) -> None:
        while self._salida and self.abierto:
            try:
                enviados = self.sock.send(self._salida)
            except (BlockingIOError, InterruptedError):
                return                                  # búfer del sistema lleno: se reintenta luego
            except OSError:
                self.cerrar()
                return
            del self._salida[:enviados]

    def recibir(self) -> List[dict]:
        """Mensajes completos que hayan llegado (sin bloquear). Si el otro lado cerró, abierto=False."""
        while self.abierto:
            try:
                trozo = self.sock.recv(65536)
            except (BlockingIOError, InterruptedError):
                break                                   # no hay más datos por ahora
            except OSError:
                self.cerrar()
                break
            if not trozo:                               # el otro lado cerró la conexión
                self.cerrar()
                break
            self._entrada += trozo
        mensajes = []
        while len(self._entrada) >= CABECERA.size:
            (largo,) = CABECERA.unpack_from(self._entrada)
            if largo > MAXIMO:
                self.cerrar()
                break
            if len(self._entrada) < CABECERA.size + largo:
                break                                   # el mensaje aún no llegó entero
            cuerpo = bytes(self._entrada[CABECERA.size:CABECERA.size + largo])
            del self._entrada[:CABECERA.size + largo]
            try:
                mensaje = json.loads(cuerpo.decode("utf-8"))
            except ValueError:
                self.cerrar()
                break
            if isinstance(mensaje, dict):
                mensajes.append(mensaje)
        return mensajes

    def cerrar(self) -> None:
        if self.abierto:
            self.abierto = False
            try:
                self.sock.close()
            except OSError:
                pass


def ip_local() -> str:
    """IP de este equipo en la red local (la que deben escribir los demás para unirse)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))            # no envía nada: solo elige la interfaz
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
